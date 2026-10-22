from importlib import import_module
from types import SimpleNamespace

from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase

from apps.submissions.models import Submission
from .models import Daily, DailySlot, DailySlotCondition


class FreshGuestBoardTests(TestCase):
    def repair(self):
        import_module('apps.dailies.migrations.0022_repair_fresh_guest_board').install(
            apps, SimpleNamespace(connection=connection))

    def board(self, **fields):
        daily = Daily.objects.create(date='2026-10-22', status='published', **fields)
        for position, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
            slot = DailySlot.objects.create(daily=daily, position=position, role=role)
            DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR')
        return daily

    def test_repair_follows_synthetic_cleanup_and_restores_the_exact_guest_board(self):
        plan = MigrationLoader(connection).graph.forwards_plan(('dailies', '0022_repair_fresh_guest_board'))
        self.assertLess(plan.index(('scoring', '0005_remove_synthetic_votes')),
                        plan.index(('dailies', '0022_repair_fresh_guest_board')))
        daily = self.board()
        slots = list(daily.slots.values_list('pk', flat=True))
        self.repair()
        daily.refresh_from_db()
        self.assertEqual(daily.author_name, 'Kaczy')
        self.assertEqual(list(daily.slots.values_list('pk', flat=True)), slots)
        self.assertEqual([s.conditions.count() for s in daily.slots.all()], [2, 2, 1, 2, 2])
        before = list(DailySlotCondition.objects.order_by('pk').values())
        self.repair()
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()), before)

    def test_repair_preserves_even_a_started_game_without_answers(self):
        daily = self.board()
        Submission.objects.create(daily=daily, guest_token='fresh-guest-protection')
        before = list(DailySlotCondition.objects.order_by('pk').values())
        self.repair()
        daily.refresh_from_db()
        self.assertEqual(daily.author_name, '')
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()), before)
        self.assertEqual(Submission.objects.get(daily=daily).guest_token, 'fresh-guest-protection')

    def test_repair_preserves_another_author(self):
        daily = self.board(author_name='Another author')
        before = list(DailySlotCondition.objects.order_by('pk').values())
        self.repair()
        daily.refresh_from_db()
        self.assertEqual(daily.author_name, 'Another author')
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()), before)
