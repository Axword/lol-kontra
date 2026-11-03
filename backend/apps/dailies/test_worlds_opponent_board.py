from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.scoring.models import AnswerStatsDaily
from apps.submissions.models import Submission, SubmissionAnswer
from .generator import _has_distinct_roster, validate_board_diversity, validate_daily
from .models import CommunityComment, Daily, DailySlot, DailySlotCondition, valid_requirement_count
from .test_match_boards import verified_players
from .validators import PlayerFacts, evaluate_condition

release = import_module('apps.dailies.migrations.0028_worlds_opponent_board_november_4')


class WorldsOpponentBoardContractTests(SimpleTestCase):
    def test_frozen_board_has_broad_exact_pools_and_a_distinct_roster(self):
        source = release.load_release()
        self.assertEqual(source['date'], '2026-11-04')
        self.assertEqual(source['opponents_through_year'], 2025)
        self.assertEqual(source['teams'], ['geng', 'lyon'])
        validate_board_diversity([slot['conditions'] for slot in source['slots']])
        players = verified_players()
        pools = []
        for slot in source['slots']:
            with self.subTest(role=slot['role']):
                self.assertTrue(valid_requirement_count([SimpleNamespace(**c) for c in slot['conditions']]))
                candidates = [p for p in players if slot['role'] in PlayerFacts(p).roles and all(
                    evaluate_condition(p, c['condition_type'], c['operator'], c['value'])
                    for c in slot['conditions'])]
                self.assertGreaterEqual(len(candidates), 18)
                self.assertEqual(sorted(p.slug for p in candidates), slot['audited_candidates'])
                pools.append(candidates)
        self.assertEqual([len(pool) for pool in pools], [31, 21, 26, 26, 29])
        self.assertTrue(_has_distinct_roster(pools))
        mid = source['slots'][2]['conditions']
        self.assertEqual([(c['condition_type'], c['operator'], c['value']) for c in mid],
                         [('worlds_opponent_team', 'eq', 'geng')])
        self.assertIn('przed 2026', mid[0]['label_pl'])
        self.assertIn('before 2026', mid[0]['label_en'])


class WorldsOpponentBoardRevisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Player.objects.bulk_create([Player(**vars(p)) for p in verified_players()], ignore_conflicts=True)

    def setUp(self):
        Daily.objects.all().delete()

    def install(self):
        release.install(apps, SimpleNamespace(connection=connection))

    def old_board(self):
        board = Daily.objects.create(date='2026-11-04', status='published')
        for position, role in enumerate(release.ROLES, 1):
            slot = DailySlot.objects.create(daily=board, position=position, role=role)
            DailySlotCondition.objects.create(slot=slot, condition_type='country', operator='eq',
                value='KR', label_pl='Koreańczyk', label_en='Korean')
        return board

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 4))
    def test_replacement_preserves_games_comments_counts_and_other_dates(self, _date):
        old = self.old_board()
        yesterday = Daily.objects.create(date='2026-11-03', status='published')
        tomorrow = Daily.objects.create(date='2026-11-05', status='published')
        player = Player.objects.get(slug='faker')
        slot = old.slots.get(role='mid')
        game = Submission.objects.create(daily=old, guest_token='opponent-old-game', total_points=37)
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=slot, player=player,
            is_correct=True, rarity_percent=0, points_awarded=-100, is_diamond_pick=True)
        stats = AnswerStatsDaily.objects.create(daily_slot=slot, player=player, pick_count=1,
            pick_percent=100, rarity_tier='common')
        comment = CommunityComment.objects.create(submission=game, text='Poprzedni skład', roster_png=b'old-image')
        before = {
            'slots': list(old.slots.values()),
            'conditions': list(DailySlotCondition.objects.filter(slot__daily=old).values()),
            'game': Submission.objects.filter(pk=game.pk).values().get(),
            'answer': SubmissionAnswer.objects.filter(pk=answer.pk).values().get(),
            'stats': AnswerStatsDaily.objects.filter(pk=stats.pk).values().get(),
            'comment': CommunityComment.objects.filter(pk=comment.pk).values().get(),
        }
        self.install()
        for row in (old, yesterday, tomorrow):
            row.refresh_from_db()
        self.assertFalse(old.is_current)
        self.assertTrue(yesterday.is_current)
        self.assertTrue(tomorrow.is_current)
        self.assertEqual(before, {
            'slots': list(old.slots.values()),
            'conditions': list(DailySlotCondition.objects.filter(slot__daily=old).values()),
            'game': Submission.objects.filter(pk=game.pk).values().get(),
            'answer': SubmissionAnswer.objects.filter(pk=answer.pk).values().get(),
            'stats': AnswerStatsDaily.objects.filter(pk=stats.pk).values().get(),
            'comment': CommunityComment.objects.filter(pk=comment.pk).values().get(),
        })
        current = Daily.objects.get(date=release.DAY, is_current=True)
        self.assertNotEqual(current.pk, old.pk)
        self.assertFalse(current.submissions.exists())
        validate_daily(current)
        client = APIClient()
        self.assertEqual(client.get('/api/v1/dailies/today/').data['id'], current.pk)
        self.assertEqual(client.get(f'/api/v1/dailies/{old.pk}/').status_code, 200)
        self.assertEqual(client.get(f'/api/v1/dailies/{tomorrow.pk}/').status_code, 404)
        counts = (Daily.objects.count(), DailySlot.objects.count(), DailySlotCondition.objects.count())
        self.install()
        self.assertEqual((Daily.objects.count(), DailySlot.objects.count(), DailySlotCondition.objects.count()), counts)

    def test_reactivating_installed_revision_does_not_create_duplicates(self):
        self.install()
        current = Daily.objects.get(date=release.DAY, is_current=True)
        current.is_current = False
        current.save(update_fields=['is_current'])
        later = self.old_board()
        self.install()
        self.assertEqual(Daily.objects.get(date=release.DAY, is_current=True).pk, current.pk)
        later.refresh_from_db()
        self.assertFalse(later.is_current)
        self.assertEqual(Daily.objects.filter(date=release.DAY).count(), 2)

    def test_incomplete_player_pack_cannot_replace_existing_board(self):
        old = self.old_board()
        missing = release.load_release()['slots'][2]['audited_candidates'][0]
        Player.objects.filter(slug=missing).delete()
        with self.assertRaisesRegex(ValueError, 'identities are missing'):
            self.install()
        old.refresh_from_db()
        self.assertTrue(old.is_current)
        self.assertEqual(Daily.objects.count(), 1)

    def test_missing_opponent_evidence_cannot_replace_existing_board(self):
        old = self.old_board()
        slug = release.load_release()['slots'][2]['audited_candidates'][0]
        player = Player.objects.get(slug=slug)
        player.attributes.pop('worlds_opponents', None)
        player.save(update_fields=['attributes'])
        with self.assertRaisesRegex(ValueError, 'opponent evidence'):
            self.install()
        old.refresh_from_db()
        self.assertTrue(old.is_current)
        self.assertEqual(Daily.objects.count(), 1)

    def test_schema_only_database_does_not_create_unanswerable_board(self):
        Player.objects.all().delete()
        self.install()
        self.assertFalse(Daily.objects.exists())
