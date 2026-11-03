from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from .generator import _has_distinct_roster, validate_daily
from .models import Daily, DailySlotCondition, valid_requirement_count
from .test_playoff_boards import released_players, player_release
from .validators import PlayerFacts, evaluate_condition

previous_release = import_module('apps.dailies.migrations.0024_worlds_playoff_boards')
release = import_module('apps.dailies.migrations.0026_historical_playoff_boards')


class HistoricalPlayoffContractTests(SimpleTestCase):
    def test_all_answer_pools_match_the_evaluator_and_have_a_distinct_roster(self):
        players = released_players()
        package = release.load_release()
        self.assertEqual(package['player_release_sha256'], player_release.RELEASE_SHA256)
        for board in package['boards']:
            pools = []
            for slot in board['slots']:
                with self.subTest(day=board['date'], role=slot['role']):
                    self.assertTrue(valid_requirement_count([SimpleNamespace(**c) for c in slot['conditions']]))
                    self.assertNotIn('LPL', [c['value'] for c in slot['conditions']])
                    candidates = [p for p in players if slot['role'] in PlayerFacts(p).roles
                        and all(evaluate_condition(p, c['condition_type'], c['operator'], c['value'])
                                for c in slot['conditions'])]
                    self.assertGreaterEqual(len(candidates), 2)
                    self.assertEqual(sorted(p.slug for p in candidates), slot['audited_candidates'])
                    pools.append(candidates)
            self.assertTrue(_has_distinct_roster(pools))

    def test_china_outside_lpl_example_uses_birthplace_and_positive_lcs_evidence(self):
        adc = release.load_release()['boards'][1]['slots'][3]
        self.assertEqual([(c['condition_type'], c['value']) for c in adc['conditions']],
                         [('birth_country', 'CN'), ('league', 'LCS')])
        self.assertEqual(len(adc['audited_candidates']), 3)
        self.assertIn('cody-sun', adc['audited_candidates'])


class HistoricalPlayoffRevisionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Player.objects.bulk_create(released_players(), ignore_conflicts=True)

    def setUp(self):
        Daily.objects.all().delete()

    def install(self, migration=release):
        migration.install(apps, SimpleNamespace(connection=connection))

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 3))
    def test_old_games_are_untouched_new_pools_validate_and_tomorrow_remains_hidden(self, _date):
        self.install(previous_release)
        old = Daily.objects.get(date='2026-11-03', is_current=True)
        tomorrow_old = Daily.objects.get(date='2026-11-04', is_current=True)
        game = Submission.objects.create(daily=old, guest_token='historical-playoff-progress', total_points=42)
        answer = SubmissionAnswer.objects.create(
            submission=game, daily_slot=old.slots.get(role='mid'), player=Player.objects.get(slug='knight-zhuo-ding'),
            is_correct=True, rarity_percent=0, points_awarded=0, is_diamond_pick=True,
        )
        before = list(DailySlotCondition.objects.filter(slot__daily=old).values())
        self.install()
        old.refresh_from_db()
        tomorrow_old.refresh_from_db()
        game.refresh_from_db()
        answer.refresh_from_db()
        self.assertFalse(old.is_current)
        self.assertFalse(tomorrow_old.is_current)
        self.assertEqual(list(DailySlotCondition.objects.filter(slot__daily=old).values()), before)
        self.assertEqual((game.daily_id, game.total_points), (old.pk, 42))
        self.assertEqual((answer.rarity_percent, answer.is_diamond_pick), (0, True))
        current = Daily.objects.get(date='2026-11-03', is_current=True)
        future = Daily.objects.get(date='2026-11-04', is_current=True)
        self.assertFalse(current.submissions.exists())
        validate_daily(current)
        validate_daily(future)
        client = APIClient()
        self.assertEqual(client.get('/api/v1/dailies/today/').data['id'], current.pk)
        self.assertEqual(client.get(f'/api/v1/dailies/{old.pk}/').status_code, 200)
        self.assertEqual(client.get(f'/api/v1/dailies/{future.pk}/').status_code, 404)
        self.assertEqual(client.get(f'/api/v1/dailies/{future.pk}/slots/').status_code, 404)
        self.assertEqual([b['id'] for b in client.get('/api/v1/dailies/').data['results']], [current.pk])
        before_counts = (Daily.objects.count(), DailySlotCondition.objects.count())
        self.install()
        self.assertEqual((Daily.objects.count(), DailySlotCondition.objects.count()), before_counts)

    def test_partial_player_pack_cannot_replace_the_current_board(self):
        self.install(previous_release)
        old = Daily.objects.get(date='2026-11-03', is_current=True)
        missing = release.load_release()['boards'][1]['slots'][3]['audited_candidates'][0]
        Player.objects.filter(slug=missing).delete()
        with self.assertRaisesRegex(ValueError, 'identities are missing'):
            self.install()
        old.refresh_from_db()
        self.assertTrue(old.is_current)
        self.assertEqual(Daily.objects.count(), 2)

    def test_schema_only_database_does_not_create_unanswerable_boards(self):
        Player.objects.all().delete()
        self.install()
        self.assertFalse(Daily.objects.exists())
