from datetime import date, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import Daily, DailySlot, DailySlotCondition


class DailyIntegrityConstraintTests(TestCase):
    def test_status_reveal_and_close_order_are_checked_on_database_writes(self):
        daily = Daily.objects.create(date=date(2020, 1, 1))
        now = timezone.now()
        for values in ({'status': 'invalid'}, {'reveal_mode': 'after_close'},
                       {'published_at': now, 'closed_at': now - timedelta(seconds=1)}):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                Daily.objects.filter(pk=daily.pk).update(**values)
        Daily.objects.filter(pk=daily.pk).update(published_at=now, closed_at=now)

    def test_date_slot_position_and_role_uniqueness_and_ranges(self):
        daily = Daily.objects.create(date=date(2020, 1, 1))
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        factories = (
            lambda: Daily.objects.create(date=daily.date),
            lambda: DailySlot.objects.create(daily=daily, position=1, role='mid'),
            lambda: DailySlot.objects.create(daily=daily, position=2, role='top'),
            lambda: DailySlot.objects.create(daily=daily, position=0, role='mid'),
            lambda: DailySlot.objects.create(daily=daily, position=6, role='mid'),
            lambda: DailySlot.objects.create(daily=daily, position=2, role='coach'),
        )
        for factory in factories:
            with self.assertRaises(IntegrityError), transaction.atomic():
                factory()
        self.assertEqual(DailySlot.objects.get(pk=slot.pk).role, 'top')

    def test_condition_operator_and_nonnegative_order_are_checked(self):
        daily = Daily.objects.create(date=date(2020, 1, 1))
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        condition = DailySlotCondition.objects.create(slot=slot, condition_type='worlds_games', operator='gt', value=25)
        for values in ({'operator': 'eval'}, {'order': -1}):
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                DailySlotCondition.objects.filter(pk=condition.pk).update(**values)
