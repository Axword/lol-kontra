from collections import Counter
from copy import deepcopy
from datetime import date
import gzip
import importlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.models import Sum
from django.test import TestCase

from apps.players.models import Player
from apps.scoring.models import AnswerStatsDaily, ScoringConfig
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt

from .migrations import _october_2026_release as calendar
from .models import Daily, DailySlot, DailySlotCondition
from .validators import player_matches_slot


players_release = importlib.import_module('apps.players.migrations.0003_release_worlds_players')


def document():
    return {'release': 'october-2026-v1', 'boards': calendar.load_calendar()}


def all_keys(value):
    if isinstance(value, dict):
        for key, nested in value.items():
            yield key
            yield from all_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from all_keys(nested)


class CalendarReleaseSourceTests(unittest.TestCase):
    def test_package_contains_all_dates_roles_requirements_and_anonymous_rosters(self):
        source = document()
        self.assertEqual([row['date'] for row in source['boards']],
                         [date(2026, 10, day).isoformat() for day in range(1, 32)])
        for board in source['boards']:
            self.assertEqual([slot['role'] for slot in board['slots']], list(calendar.ROLES))
            self.assertEqual([slot['position'] for slot in board['slots']], [1, 2, 3, 4, 5])
            self.assertTrue(all(len(slot['conditions']) == 2 for slot in board['slots']))
            self.assertEqual(len(board['test_rosters']), 10)
            for roster in board['test_rosters']:
                self.assertEqual(set(roster), set(calendar.ROLES))
                self.assertEqual(len(set(roster.values())), 5)
        forbidden = {'id', 'pk', 'user', 'user_id', 'username', 'email', 'password',
                     'guest_token', 'ip_hash', 'submitted_at', 'answers', 'attempts'}
        self.assertFalse(set(all_keys(source)) & forbidden)

    def test_changed_release_bytes_fail_checksum_before_parsing(self):
        with patch.object(Path, 'read_bytes', return_value=gzip.compress(b'{}', mtime=0)):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                calendar.load_calendar()

    def test_private_user_payload_is_rejected_even_in_an_otherwise_valid_document(self):
        source = document()
        source['boards'][0]['guest_token'] = 'private-user-token'
        with self.assertRaisesRegex(ValueError, 'unexpected board fields'):
            calendar.validate_calendar(source)

    def test_one_requirement_or_repeated_player_cannot_enter_a_release(self):
        source = document()
        source['boards'][0]['slots'][0]['conditions'].pop()
        with self.assertRaisesRegex(ValueError, 'two requirements'):
            calendar.validate_calendar(source)
        source = document()
        roster = source['boards'][0]['test_rosters'][0]
        roster['jungle'] = roster['top']
        with self.assertRaisesRegex(ValueError, 'five different players'):
            calendar.validate_calendar(source)


class CalendarReleaseInstallTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.historical_apps = MigrationLoader(connection).project_state([
            ('dailies', '0009_october_2026_release')
        ]).apps
        cls.editor = SimpleNamespace(connection=connection)

    def setUp(self):
        # Exercise the actual frozen RunPython with historical apps, without
        # changing the migration recorder or importing runtime seed services.
        players_release.Migration.operations[0].code(self.historical_apps, self.editor)

    def test_fresh_install_has_complete_seed_rosters_valid_answers_and_pick_populations(self):
        calendar.install_calendar(self.historical_apps, self.editor)
        self.assertEqual((Daily.objects.count(), DailySlot.objects.count(), DailySlotCondition.objects.count()),
                         (31, 155, 310))
        self.assertEqual((Submission.objects.count(), SubmissionAnswer.objects.count(), SubmissionAttempt.objects.count()),
                         (310, 1550, 1550))
        self.assertEqual(ScoringConfig.objects.filter(is_active=True).count(), 1)
        self.assertFalse(Submission.objects.filter(is_seed=False).exists())
        self.assertFalse(Submission.objects.filter(user__isnull=False).exists())
        self.assertFalse(Submission.objects.exclude(ip_hash='').exists())
        board_votes = Counter(Submission.objects.values_list('daily_id', flat=True))
        self.assertEqual(len(board_votes), 31)
        self.assertEqual(set(board_votes.values()), {10})
        rosters = {}
        slots = {slot.pk: slot for slot in DailySlot.objects.prefetch_related('conditions')}
        for answer in SubmissionAnswer.objects.select_related('player'):
            rosters.setdefault(answer.submission_id, set()).add(answer.player_id)
            # Frozen historical picks retain their original acceptance even
            # when a later role policy rejects the same new guess.
            self.assertTrue(answer.is_correct)
        self.assertTrue(all(len(players) == 5 for players in rosters.values()))
        populations = AnswerStatsDaily.objects.values('daily_slot_id').annotate(
            votes=Sum('pick_count'), percent=Sum('pick_percent'))
        self.assertEqual(len(populations), 155)
        self.assertTrue(all(row['votes'] == 10 and row['percent'] == 100 for row in populations))

    def test_replay_preserves_existing_board_ids_real_guest_progress_and_never_seeds_that_date(self):
        daily = Daily.objects.create(date=date(2026, 10, 7), status='published', locale_seed='owned-by-real-game')
        for position, role in enumerate(calendar.ROLES, 1):
            slot = DailySlot.objects.create(daily=daily, position=position, role=role,
                                           label_pl='Własna plansza', label_en='Existing board')
            for order, (kind, operator, value) in enumerate((('worlds_count_min', 'gte', 1), ('worlds_champion', 'eq', True))):
                DailySlotCondition.objects.create(slot=slot, condition_type=kind, operator=operator, value=value,
                                                  order=order, label_pl='Własny warunek', label_en='Existing requirement')
        player = Player.objects.get(slug='faker')
        game = Submission.objects.create(daily=daily, guest_token='real-guest-private-token', errors_used=2,
                                         is_seed=False, total_points=480)
        slot = daily.slots.get(role='mid')
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True,
            points_awarded=-20, rarity_percent=20, scoring_pick_count=1, scoring_sample_size=5)
        attempt = SubmissionAttempt.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
        self.assertTrue(player_matches_slot(player, slot))

        def preserved_state():
            return {
                'daily': Daily.objects.filter(pk=daily.pk).values().get(),
                'slots': list(DailySlot.objects.filter(daily=daily).order_by('pk').values()),
                'conditions': list(DailySlotCondition.objects.filter(slot__daily=daily).order_by('pk').values()),
                'submission': Submission.objects.filter(pk=game.pk).values().get(),
                'answer': SubmissionAnswer.objects.filter(pk=answer.pk).values().get(),
                'attempt': SubmissionAttempt.objects.filter(pk=attempt.pk).values().get(),
            }

        before = deepcopy(preserved_state())
        calendar.install_calendar(self.historical_apps, self.editor)
        self.assertEqual(preserved_state(), before)
        self.assertEqual(Daily.objects.count(), 31)
        self.assertEqual(Submission.objects.filter(is_seed=True).count(), 300)
        self.assertFalse(Submission.objects.filter(daily=daily, is_seed=True).exists())
        self.assertFalse(AnswerStatsDaily.objects.filter(daily_slot__daily=daily).exists())
        board_ids = dict(Daily.objects.values_list('date', 'pk'))
        game_ids = set(Submission.objects.values_list('pk', flat=True))
        calendar.install_calendar(self.historical_apps, self.editor)
        self.assertEqual(preserved_state(), before)
        self.assertEqual(dict(Daily.objects.values_list('date', 'pk')), board_ids)
        self.assertEqual(set(Submission.objects.values_list('pk', flat=True)), game_ids)

    def test_missing_verified_player_aborts_before_calendar_or_scoring_config_is_written(self):
        required_slug = calendar.load_calendar()[0]['test_rosters'][0]['top']
        Player.objects.filter(slug=required_slug).update(attributes={'worlds_verified': False})
        with self.assertRaisesRegex(ValueError, 'missing verified player identities'):
            calendar.install_calendar(self.historical_apps, self.editor)
        self.assertFalse(Daily.objects.exists())
        self.assertFalse(Submission.objects.exists())
        self.assertFalse(ScoringConfig.objects.exists())
