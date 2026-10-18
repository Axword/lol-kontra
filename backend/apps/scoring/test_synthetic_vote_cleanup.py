from datetime import timedelta
import importlib
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.utils import timezone

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from apps.users.models import UserStats
from .models import AnswerStatsDaily


cleanup = importlib.import_module('apps.scoring.migrations.0005_remove_synthetic_votes')


class SyntheticVoteCleanupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='human-owner')
        self.players = [Player.objects.create(slug=f'person-{i}', nickname=f'Person {i}') for i in range(4)]
        self.current = self.board(0, 'published')
        self.past = self.board(-1, 'scored')
        self.future = self.board(1, 'published')

    def board(self, offset, status):
        board = Daily.objects.create(date=timezone.localdate()+timedelta(days=offset), status=status)
        for position, role in enumerate(('top', 'mid'), 1):
            DailySlot.objects.create(daily=board, position=position, role=role)
        return board

    def game(self, board, token=None, user=None, seed=False, practice=False, scored=False, errors=0, players=None):
        game = Submission.objects.create(
            daily=board, guest_token=token, user=user, is_seed=seed,
            is_practice=practice, is_scored=scored, errors_used=errors, total_points=300,
        )
        for slot, player in zip(board.slots.all(), players or self.players[:2]):
            SubmissionAnswer.objects.create(
                submission=game, daily_slot=slot, player=player, is_correct=True,
                rarity_percent=100, rarity_tier='common', points_awarded=-100,
                scoring_pick_count=10, scoring_sample_size=10,
            )
            SubmissionAttempt.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
        return game

    def test_cleanup_rebuilds_real_snapshots_without_changing_historical_human_results(self):
        # A real token resembling a seed is retained: marker, never token text,
        # decides which rows are synthetic.
        open_game = self.game(self.current, token='seed-real-human', errors=2, players=self.players[:1])
        Submission.objects.filter(pk=open_game.pk).update(total_points=400)
        open_game.answers.update(rarity_percent=41.7, points_awarded=-41.7,
                                 scoring_pick_count=417, scoring_sample_size=1000)
        wrong_slot = self.current.slots.last()
        SubmissionAnswer.objects.create(submission=open_game, daily_slot=wrong_slot,
                                        player=self.players[2], is_correct=False)
        SubmissionAttempt.objects.create(submission=open_game, daily_slot=wrong_slot,
                                         player=self.players[2], is_correct=False)
        owner = self.game(self.past, user=self.user, scored=True)
        other = self.game(self.past, token='other-real-human', scored=True, players=self.players[2:])
        practice = self.game(self.past, user=self.user, practice=True, scored=True)
        UserStats.objects.filter(user=self.user).update(
            games_played=1, total_points=300, avg_points=300, best_score=300,
            current_streak=1, max_streak=1,
        )
        for index, board in enumerate((self.current, self.past, self.future)):
            self.game(board, token=f'old-ai-{index}', seed=True)
        for board in (self.current, self.past, self.future):
            for slot, player in zip(board.slots.all(), self.players[:2]):
                AnswerStatsDaily.objects.create(daily_slot=slot, player=player, pick_count=10,
                                               pick_percent=100, rarity_tier='common')

        def preserved():
            return {
                'boards': list(Daily.objects.order_by('pk').values()),
                'slots': list(DailySlot.objects.order_by('pk').values()),
                'games': list(Submission.objects.filter(is_seed=False).order_by('pk').values()),
                'answers': list(SubmissionAnswer.objects.filter(submission__is_seed=False).order_by('pk').values()),
                'attempts': list(SubmissionAttempt.objects.filter(submission__is_seed=False).order_by('pk').values()),
                'users': list(get_user_model().objects.order_by('pk').values()),
                'user_stats': list(UserStats.objects.order_by('pk').values()),
            }

        before = preserved()
        historical_apps = MigrationLoader(connection).project_state([
            ('scoring', '0005_remove_synthetic_votes'),
        ]).apps
        for _ in range(2):
            cleanup.remove_synthetic_votes(historical_apps, SimpleNamespace(connection=connection))
            self.assertEqual(preserved(), before)
            self.assertEqual(Submission.objects.count(), 4)
            self.assertFalse(Submission.objects.filter(is_seed=True).exists())
            self.assertEqual(SubmissionAnswer.objects.count(), 8)
            self.assertEqual(SubmissionAttempt.objects.count(), 8)
            open_game.refresh_from_db()
            self.assertEqual((open_game.total_points, open_game.errors_used, open_game.is_scored), (400, 2, False))
            answer = open_game.answers.get(is_correct=True)
            self.assertEqual((answer.rarity_percent, answer.points_awarded,
                              answer.scoring_pick_count, answer.scoring_sample_size), (41.7, -41.7, 417, 1000))
            for game in (owner, other, practice):
                game.refresh_from_db()
                self.assertEqual(game.total_points, 300)
                self.assertEqual(list(game.answers.values_list('rarity_percent', flat=True)), [100, 100])
            self.assertEqual(AnswerStatsDaily.objects.count(), 5)
            self.assertFalse(AnswerStatsDaily.objects.filter(daily_slot__daily=self.future).exists())
            live_snapshot = AnswerStatsDaily.objects.filter(daily_slot__daily=self.current).get()
            self.assertEqual((live_snapshot.pick_count, live_snapshot.pick_percent), (1, 100))
            stats = UserStats.objects.get(user=self.user)
            self.assertEqual((stats.games_played, stats.total_points, stats.avg_points, stats.best_score), (1, 300, 300, 300))
            self.assertEqual((stats.legendary_answers, stats.diamond_picks, stats.current_streak, stats.max_streak), (0, 0, 1, 1))

    def test_unaffected_games_and_snapshot_values_are_preserved(self):
        # Only dates containing marked votes need a new scoring population.
        # A different historical board can retain its original real result.
        unrelated = self.board(-2, 'published')
        human = self.game(unrelated, user=self.user, scored=True)
        Submission.objects.filter(pk=human.pk).update(total_points=450)
        snapshot = AnswerStatsDaily.objects.create(daily_slot=unrelated.slots.first(), player=self.players[0],
                                                  pick_count=1, pick_percent=75, rarity_tier='common')
        self.game(self.current, token='retired-ai', seed=True)
        before_game = Submission.objects.filter(pk=human.pk).values().get()
        before_answers = list(human.answers.order_by('pk').values())
        before_snapshot = AnswerStatsDaily.objects.filter(pk=snapshot.pk).values().get()
        historical_apps = MigrationLoader(connection).project_state([
            ('scoring', '0005_remove_synthetic_votes'),
        ]).apps
        cleanup.remove_synthetic_votes(historical_apps, SimpleNamespace(connection=connection))
        self.assertEqual(Submission.objects.filter(pk=human.pk).values().get(), before_game)
        self.assertEqual(list(human.answers.order_by('pk').values()), before_answers)
        self.assertEqual(AnswerStatsDaily.objects.filter(pk=snapshot.pk).values().get(), before_snapshot)
