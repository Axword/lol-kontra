import importlib
from datetime import timedelta

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.utils import timezone

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.scoring.engine import recalc_submission_total
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt


class SumSavedPercentageTests(TestCase):
    def setUp(self):
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slots = [DailySlot.objects.create(daily=self.daily, position=i + 1, role=role)
                      for i, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'])]
        self.players = [Player.objects.create(slug=f'sum-player-{i}', nickname=f'Player {i}', primary_role=slot.role)
                        for i, slot in enumerate(self.slots)]

    def answers(self, game, percentages):
        for index, percent in enumerate(percentages):
            answer = SubmissionAnswer.objects.create(
                submission=game, daily_slot=self.slots[index], player=self.players[index],
                is_correct=True, rarity_percent=percent, points_awarded=-(percent or 0),
            )
            SubmissionAttempt.objects.create(submission=game, daily_slot=answer.daily_slot, player=answer.player, is_correct=True)

    def test_five_saved_percentages_sum_to_fifteen_and_five_firsts_to_zero(self):
        for token, percentages, expected in [('sum-fifteen', [1, 2, 3, 4, 5], 15), ('sum-zero', [0] * 5, 0)]:
            game = Submission.objects.create(daily=self.daily, guest_token=token)
            self.answers(game, percentages)
            self.assertEqual(recalc_submission_total(game), expected)

    def test_missing_answers_keep_their_cost_before_and_after_game_over(self):
        game = Submission.objects.create(daily=self.daily, guest_token='sum-missing')
        self.assertEqual(recalc_submission_total(game), 500)
        self.answers(game, [0, 10])
        self.assertEqual(recalc_submission_total(game), 310)
        game.errors_used = 10
        game.save(update_fields=['errors_used'])
        self.assertEqual(recalc_submission_total(game), 310)
        self.assertEqual(list(game.answers.values_list('rarity_percent', flat=True)), [0, 10])

    def test_explicit_migration_changes_only_scores_and_is_idempotent(self):
        user = get_user_model().objects.create_user(username='sum-migration')
        game = Submission.objects.create(daily=self.daily, user=user, total_points=485, is_scored=True, errors_used=2)
        self.answers(game, [1, 2, 3, 4, 5])
        first = game.answers.get(daily_slot=self.slots[0])
        first.is_diamond_pick = True
        first.diamond_awarded_at = timezone.now() - timedelta(hours=1)
        first.save(update_fields=['is_diamond_pick', 'diamond_awarded_at'])
        protected_fields = ['pk', 'submission_id', 'daily_slot_id', 'player_id', 'is_correct', 'rarity_percent',
                            'rarity_tier', 'is_diamond_pick', 'diamond_awarded_at', 'scoring_pick_count', 'scoring_sample_size']
        saved_answers = list(game.answers.order_by('pk').values(*protected_fields))
        saved_attempts = list(game.attempts.order_by('pk').values())
        saved_game = Submission.objects.filter(pk=game.pk).values().get()
        migrate = importlib.import_module('apps.scoring.migrations.0007_sum_pick_percentages').recalculate_saved_scores
        for _ in range(2):
            migrate(apps, connection.schema_editor())
            game.refresh_from_db()
            self.assertEqual(game.total_points, 15)
            self.assertEqual(list(game.answers.order_by('pk').values_list('points_awarded', flat=True)), [-99, -98, -97, -96, -95])
            self.assertEqual(list(game.answers.order_by('pk').values(*protected_fields)), saved_answers)
            self.assertEqual(list(game.attempts.order_by('pk').values()), saved_attempts)
            actual = Submission.objects.filter(pk=game.pk).values().get()
            self.assertEqual({k: v for k, v in actual.items() if k != 'total_points'},
                             {k: v for k, v in saved_game.items() if k != 'total_points'})
            user.stats.refresh_from_db()
            self.assertEqual((user.stats.total_points, user.stats.best_score), (15, 15))

    def test_unknown_legacy_percent_does_not_become_a_free_correct_pick(self):
        game = Submission.objects.create(daily=self.daily, guest_token='sum-unknown')
        self.answers(game, [None])
        self.assertEqual(recalc_submission_total(game), 500)
        self.assertIsNone(game.answers.get().rarity_percent)

    def test_a_legacy_board_without_positions_is_not_a_free_perfect_score(self):
        empty = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='published')
        game = Submission.objects.create(daily=empty, guest_token='sum-empty')
        self.assertEqual(recalc_submission_total(game), 500)
