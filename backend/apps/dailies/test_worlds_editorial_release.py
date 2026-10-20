from datetime import date
from importlib import import_module
from io import StringIO
from types import SimpleNamespace

from django.apps import apps
from django.core.management import call_command
from django.db import connection
from django.test import TestCase

from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from .board_factory import is_worlds
from .generator import count_candidates, validate_daily
from .models import Daily, DailySlot, DailySlotCondition

release = import_module('apps.dailies.migrations.0020_worlds_focused_future_boards')


class WorldsEditorialReleaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_players', full=True, stdout=StringIO())
        from .migrations._guest_board_2026 import install
        install(apps, SimpleNamespace(connection=connection))
        from .migrations._minimum_ten_boards import install as previous
        previous(apps, SimpleNamespace(connection=connection), today=date(2026, 10, 20))

    def install(self):
        release.install(apps, SimpleNamespace(connection=connection))

    def test_reviewed_boards_are_playable_and_guest_author_is_unchanged(self):
        guest = Daily.objects.get(date='2026-10-22')
        guest_before = list(DailySlotCondition.objects.filter(slot__daily=guest).order_by('pk').values())
        slot_ids = list(DailySlot.objects.order_by('pk').values_list('pk', flat=True))
        self.install()
        before = list(DailySlotCondition.objects.order_by('pk').values())
        self.install()
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()), before)
        import_module('apps.dailies.migrations.0021_activity_future_boards').install(
            apps, SimpleNamespace(connection=connection))
        for daily in Daily.objects.exclude(pk=guest.pk):
            validate_daily(daily)
            slots = list(daily.slots.prefetch_related('conditions'))
            self.assertEqual(sum(any(is_worlds(c.condition_type) for c in slot.conditions.all()) for slot in slots), 3)
            self.assertTrue(all(len(count_candidates(slot)) >= 10 for slot in slots))
            self.assertFalse(daily.slots.filter(conditions__condition_type='career_top5_champion').exists())
        self.assertEqual(list(DailySlot.objects.order_by('pk').values_list('pk', flat=True)), slot_ids)
        self.assertEqual(list(DailySlotCondition.objects.filter(slot__daily=guest).order_by('pk').values()), guest_before)

    def test_started_future_board_preserves_conditions_answers_and_attempts(self):
        daily = Daily.objects.get(date='2026-10-21')
        slot = daily.slots.first()
        player = count_candidates(slot)[0]
        game = Submission.objects.create(daily=daily, guest_token='preserve-editorial-game')
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
        attempt = SubmissionAttempt.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
        before = list(DailySlotCondition.objects.filter(slot__daily=daily).order_by('pk').values())
        answer_before = SubmissionAnswer.objects.filter(pk=answer.pk).values().get()
        attempt_before = SubmissionAttempt.objects.filter(pk=attempt.pk).values().get()
        self.install()
        self.assertEqual(list(DailySlotCondition.objects.filter(slot__daily=daily).order_by('pk').values()), before)
        self.assertEqual(SubmissionAnswer.objects.filter(pk=answer.pk).values().get(), answer_before)
        self.assertEqual(SubmissionAttempt.objects.filter(pk=attempt.pk).values().get(), attempt_before)
