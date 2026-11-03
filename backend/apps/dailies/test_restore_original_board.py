from datetime import date
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from .models import Daily, DailySlot, DailySlotCondition
from .test_playoff_boards import released_players

release = import_module('apps.dailies.migrations.0027_restore_original_november_3')


class RestoreOriginalBoardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Player.objects.bulk_create(released_players(), ignore_conflicts=True)

    def setUp(self):
        Daily.objects.all().delete()

    def restore(self):
        release.restore(apps, SimpleNamespace(connection=connection))

    def original(self):
        board = Daily.objects.create(date=release.DAY, status='published', is_current=False)
        for slot in release.load_release()['slots']:
            row = DailySlot.objects.create(daily=board,
                **{key: slot[key] for key in ('position', 'role', 'label_pl', 'label_en')})
            DailySlotCondition.objects.bulk_create([DailySlotCondition(slot=row, **c) for c in slot['conditions']])
        return board

    @patch('django.utils.timezone.localdate', return_value=date(2026, 11, 3))
    def test_restores_original_ids_and_games_without_touching_replacements_or_tomorrow(self, _date):
        original = self.original()
        replacement = Daily.objects.create(date=release.DAY, status='published')
        tomorrow = Daily.objects.create(date='2026-11-04', status='published')
        game = Submission.objects.create(daily=original, guest_token='original-board-guest', total_points=25)
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=original.slots.first(),
            player=Player.objects.get(slug='faker'), is_correct=True, rarity_percent=0,
            points_awarded=0, is_diamond_pick=True)
        later_game = Submission.objects.create(daily=replacement, guest_token='replacement-board-guest', total_points=60)
        frozen = list(original.slots.values_list('pk', flat=True)), list(DailySlotCondition.objects.filter(slot__daily=original).values())
        count = Daily.objects.count()
        self.restore()
        for row in (original, replacement, tomorrow, game, answer, later_game):
            row.refresh_from_db()
        self.assertTrue(original.is_current)
        self.assertFalse(replacement.is_current)
        self.assertTrue(tomorrow.is_current)
        self.assertEqual((game.daily_id, game.total_points, answer.rarity_percent, answer.is_diamond_pick),
                         (original.pk, 25, 0, True))
        self.assertEqual((later_game.daily_id, later_game.total_points), (replacement.pk, 60))
        self.assertEqual(frozen, (list(original.slots.values_list('pk', flat=True)),
            list(DailySlotCondition.objects.filter(slot__daily=original).values())))
        client = APIClient()
        self.assertEqual(client.get('/api/v1/dailies/today/').data['id'], original.pk)
        self.assertEqual(client.get(f'/api/v1/dailies/{replacement.pk}/').status_code, 200)
        self.restore()
        self.assertEqual(Daily.objects.count(), count)

    def test_fresh_install_reconstructs_original_without_copying_game_data(self):
        previous = Daily.objects.create(date=release.DAY, status='published')
        self.restore()
        current = Daily.objects.get(date=release.DAY, is_current=True)
        self.assertNotEqual(current.pk, previous.pk)
        self.assertEqual(release.definition(current), release.load_release()['slots'])
        self.assertFalse(current.submissions.exists())
        self.restore()
        self.assertEqual(Daily.objects.count(), 2)

    def test_schema_only_database_is_unchanged(self):
        Player.objects.all().delete()
        self.restore()
        self.assertFalse(Daily.objects.exists())
