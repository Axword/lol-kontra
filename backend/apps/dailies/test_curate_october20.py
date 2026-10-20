from datetime import date
from io import StringIO
from unittest.mock import patch
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.submissions.models import Submission
from .generator import count_candidates, validate_daily
from .management.commands.curate_october20 import BOARD, ORIGINAL
from .models import Daily, DailySlot, DailySlotCondition


class CuratedOctober20Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_players', full=True, stdout=StringIO())
        from .migrations._guest_board_2026 import install
        install(apps, SimpleNamespace(connection=connection))

    def setUp(self):
        self.daily = Daily.objects.create(date=date(2026, 10, 20), status='published', minimum_candidates=None)
        for pos, (role, clues) in enumerate(zip(['top', 'jungle', 'mid', 'adc', 'support'], ORIGINAL), 1):
            slot = DailySlot.objects.create(daily=self.daily, position=pos, role=role)
            for order, (kind, op, value) in enumerate(clues):
                DailySlotCondition.objects.create(slot=slot, order=order, condition_type=kind, operator=op, value=value)

    def snapshot(self):
        return list(DailySlotCondition.objects.filter(slot__daily=self.daily).order_by('pk').values())

    def test_preview_and_failed_validation_save_nothing(self):
        before = self.snapshot()
        call_command('curate_october20', stdout=StringIO())
        self.assertEqual(before, self.snapshot())
        with patch('apps.dailies.management.commands.curate_october20.validate_daily', side_effect=ValueError('invalid')):
            with self.assertRaises(ValueError):
                call_command('curate_october20', apply=True, stdout=StringIO())
        self.assertEqual(before, self.snapshot())

    def test_apply_is_playable_idempotent_and_preserves_slots(self):
        ids = list(self.daily.slots.values_list('pk', flat=True))
        call_command('curate_october20', apply=True, stdout=StringIO())
        self.assertEqual(validate_daily(self.daily), self.daily)
        self.assertEqual(ids, list(self.daily.slots.values_list('pk', flat=True)))
        self.assertEqual([s.conditions.count() for s in self.daily.slots.all()], [1, 1, 1, 2, 1])
        self.assertEqual(len(count_candidates(self.daily.slots.get(role='top'))), 20)
        self.assertFalse(self.daily.slots.filter(conditions__condition_type='birth_year_range').exists())
        self.assertEqual([list(s.conditions.values_list('condition_type', 'operator', 'value')) for s in self.daily.slots.all()],
                         [[c[:3] for c in row] for row in BOARD])
        before = self.snapshot()
        call_command('curate_october20', apply=True, stdout=StringIO())
        self.assertEqual(before, self.snapshot())

    def test_started_or_unexpected_board_is_never_overwritten(self):
        before = self.snapshot()
        Submission.objects.create(daily=self.daily, guest_token='keep-my-game')
        with self.assertRaisesRegex(CommandError, 'Games already exist'):
            call_command('curate_october20', apply=True, stdout=StringIO())
        self.assertEqual(before, self.snapshot())
        self.daily.submissions.all().delete()
        condition = self.daily.slots.first().conditions.first()
        condition.value = 'Gnar'
        condition.save()
        before = self.snapshot()
        with self.assertRaisesRegex(CommandError, 'differs'):
            call_command('curate_october20', apply=True, stdout=StringIO())
        self.assertEqual(before, self.snapshot())
