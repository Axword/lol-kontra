from datetime import date
from importlib import import_module
from io import StringIO
from types import SimpleNamespace

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from apps.submissions.models import Submission
from .generator import count_candidates, validate_daily
from .migrations import _minimum_ten_boards as release
from .models import Daily, DailySlot, DailySlotCondition


class MinimumTenReleaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_players', full=True, stdout=StringIO())
        from .migrations._guest_board_2026 import install
        install(apps, SimpleNamespace(connection=connection))

    def install(self):
        release.install(apps, SimpleNamespace(connection=connection), today=date(2026, 10, 20))

    def test_all_ten_standard_boards_have_ten_answers_and_guest_is_preserved(self):
        guest = Daily.objects.get(date=date(2026, 10, 22))
        before = list(DailySlotCondition.objects.filter(slot__daily=guest).values())
        self.install()
        self.assertEqual(len(release.load_boards()), 10)
        snapshot = list(DailySlotCondition.objects.order_by('pk').values())
        self.install()
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()), snapshot)
        # The frozen prior release is superseded before applying today's role
        # policy to its pools. The new release has its own preservation tests.
        import_module('apps.dailies.migrations.0020_worlds_focused_future_boards').install(
            apps, SimpleNamespace(connection=connection))
        for spec in release.load_boards():
            board = Daily.objects.get(date=spec['date'])
            self.assertEqual(board.minimum_candidates, 10)
            validate_daily(board)
            self.assertTrue(all(len(count_candidates(slot)) >= 10 for slot in board.slots.all()))
            self.assertFalse(board.slots.filter(conditions__condition_type='birth_year_range').exists())
        self.assertEqual(list(DailySlotCondition.objects.filter(slot__daily=guest).values()), before)

    def test_started_board_and_today_are_preserved(self):
        board = Daily.objects.create(date=date(2026, 10, 21), status='published', minimum_candidates=None)
        slot = DailySlot.objects.create(daily=board, role='top', position=1)
        condition = DailySlotCondition.objects.create(slot=slot, condition_type='worlds_title_on_debut', value=True,
                                                      label_pl='Old label', label_en='Old label')
        Submission.objects.create(daily=board, guest_token='keep-started-game')
        today = Daily.objects.create(date=date(2026, 10, 20), minimum_candidates=None)
        self.install()
        board.refresh_from_db(); today.refresh_from_db()
        self.assertIsNone(board.minimum_candidates)
        self.assertIsNone(today.minimum_candidates)
        self.assertEqual(board.slots.count(), 1)
        self.assertTrue(DailySlotCondition.objects.filter(pk=condition.pk, label_pl='Old label').exists())
        # The separate wording migration changes labels even on a started board, without changing its rules or IDs.
        import_module('apps.dailies.migrations.0015_candidate_policy').clarify_debut(apps, SimpleNamespace(connection=connection))
        condition.refresh_from_db()
        self.assertEqual(condition.label_pl, 'Wygrał Worlds będąc debiutantem turnieju')
        self.assertEqual((condition.condition_type, condition.value, condition.slot_id), ('worlds_title_on_debut', True, slot.pk))
