from copy import deepcopy
from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection, IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.players.career_roles import with_verified_career_roles
from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from .generator import _has_distinct_roster, validate_daily, generate_daily
from .models import Daily, DailySlot, DailySlotCondition, valid_requirement_count
from .validators import PlayerFacts, evaluate_condition

release = import_module('apps.dailies.migrations.0024_worlds_playoff_boards')
player_release = import_module('apps.players.migrations.0005_worlds_2026_october_19_release')


def released_players():
    return [Player(pk=index + 1, **with_verified_career_roles(deepcopy(row)))
            for index, row in enumerate(player_release.load_release())]


class PlayoffReleaseContractTests(SimpleTestCase):
    def test_every_audited_answer_matches_the_real_rules_and_the_rosters_are_distinct(self):
        players = released_players()
        self.assertEqual(release.load_release()['player_release_sha256'], player_release.RELEASE_SHA256)
        for board in release.load_release()['boards']:
            pools = []
            for slot in board['slots']:
                self.assertTrue(valid_requirement_count([SimpleNamespace(**c) for c in slot['conditions']]))
                matching = [p for p in players if slot['role'] in PlayerFacts(p).roles
                    and all(evaluate_condition(p, c['condition_type'], c['operator'], c['value'])
                            for c in slot['conditions'])]
                self.assertGreaterEqual(len(matching), 3)
                self.assertEqual(sorted(p.slug for p in matching), slot['audited_candidates'])
                self.assertTrue(any(c['condition_type'] in {
                    'worlds_final', 'worlds_semifinal', 'worlds_final_lost',
                    'worlds_final_lost_to_faker', 'worlds_titles_exact', 'worlds_eliminated_stage',
                } for c in slot['conditions']))
                pools.append(matching)
            self.assertTrue(_has_distinct_roster(pools))


class PlayoffBoardRevisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Player.objects.bulk_create(released_players())

    def install(self):
        release.install(apps, SimpleNamespace(connection=connection))

    def old_board(self):
        board = Daily.objects.create(date='2026-11-03', status='published')
        for position, role in enumerate(release.ROLES, 1):
            slot = DailySlot.objects.create(daily=board, role=role, position=position)
            DailySlotCondition.objects.create(slot=slot, condition_type='country', operator='eq',
                value='KR', label_pl='Koreańczyk', label_en='Korean')
        return board

    def test_replacement_keeps_all_existing_answers_slots_and_scores(self):
        old = self.old_board()
        game = Submission.objects.create(daily=old, guest_token='playoff-existing-player', total_points=400)
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=old.slots.get(role='mid'),
            player=Player.objects.get(slug='faker'), is_correct=True, rarity_percent=0,
            points_awarded=-100, is_diamond_pick=True)
        before = list(old.slots.values_list('pk', flat=True))
        conditions = list(DailySlotCondition.objects.filter(slot__daily=old).values())
        self.install()
        old.refresh_from_db()
        game.refresh_from_db()
        answer.refresh_from_db()
        self.assertFalse(old.is_current)
        self.assertEqual(game.daily_id, old.pk)
        self.assertEqual(game.total_points, 400)
        self.assertEqual(answer.rarity_percent, 0)
        self.assertTrue(answer.is_diamond_pick)
        self.assertEqual(list(old.slots.values_list('pk', flat=True)), before)
        self.assertEqual(list(DailySlotCondition.objects.filter(slot__daily=old).values()), conditions)
        new = Daily.objects.get(date='2026-11-03', is_current=True)
        self.assertNotEqual(old.pk, new.pk)
        self.assertFalse(new.submissions.exists())
        validate_daily(new)
        validate_daily(Daily.objects.get(date='2026-11-04', is_current=True))
        counts = (Daily.objects.count(), DailySlot.objects.count(), DailySlotCondition.objects.count())
        self.install()
        self.assertEqual((Daily.objects.count(), DailySlot.objects.count(), DailySlotCondition.objects.count()), counts)

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 3))
    def test_calendar_today_and_generation_use_current_revision_but_old_links_still_work(self, _date):
        old = self.old_board()
        self.install()
        current = Daily.objects.get(date='2026-11-03', is_current=True)
        future = Daily.objects.get(date='2026-11-04', is_current=True)
        client = APIClient()
        self.assertEqual(client.get('/api/v1/dailies/today/').data['id'], current.pk)
        self.assertEqual(generate_daily(date=date(2026, 11, 3)).pk, current.pk)
        data = client.get('/api/v1/dailies/').data['results']
        self.assertEqual([item['id'] for item in data], [current.pk])
        self.assertEqual(client.get(f'/api/v1/dailies/{old.pk}/').status_code, 200)
        self.assertFalse(client.get(f'/api/v1/dailies/{old.pk}/').data['is_current'])
        self.assertEqual(client.get(f'/api/v1/dailies/{future.pk}/').status_code, 404)
        self.assertEqual(client.get(f'/api/v1/dailies/{future.pk}/slots/').status_code, 404)

    def test_only_one_current_revision_is_allowed_per_date(self):
        self.old_board()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Daily.objects.create(date='2026-11-03')
        Daily.objects.create(date='2026-11-03', is_current=False)

    def test_missing_source_identity_leaves_existing_board_untouched(self):
        old = self.old_board()
        Player.objects.filter(slug=release.load_release()['boards'][0]['slots'][0]['audited_candidates'][0]).delete()
        with self.assertRaisesRegex(ValueError, 'identities are missing'):
            self.install()
        old.refresh_from_db()
        self.assertTrue(old.is_current)
        self.assertEqual(Daily.objects.count(), 1)

    def test_schema_only_database_does_not_publish_unanswerable_boards(self):
        Player.objects.all().delete()
        self.install()
        self.assertFalse(Daily.objects.exists())

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 4))
    @patch('apps.scoring.tasks.score_daily')
    def test_nightly_scoring_finalizes_both_revisions_without_ambiguous_date_lookup(self, score, _date):
        from apps.scoring.tasks import nightly_scoring
        old = self.old_board()
        self.install()
        current = Daily.objects.get(date='2026-11-03', is_current=True)
        nightly_scoring.run()
        self.assertEqual([call.args[0] for call in score.call_args_list], [old.pk, current.pk])
        self.assertEqual(set(Daily.objects.filter(date='2026-11-03').values_list('status', flat=True)), {'scored'})
