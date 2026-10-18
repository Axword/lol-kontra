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
from apps.submissions.models import Submission, SubmissionAnswer
from .models import AnswerStatsDaily, ScoringConfig


rarity_migration = importlib.import_module('apps.scoring.migrations.0004_display_rarity_thresholds')


class RarityMigrationTests(TestCase):
    def test_relabels_existing_percentages_without_changing_scores_or_progress(self):
        user = get_user_model().objects.create_user(username='rarity-migration')
        player = Player.objects.create(slug='rarity-mid', nickname='Mid', primary_role='mid')
        active = ScoringConfig.objects.create(threshold_rare=20, threshold_epic=10, threshold_legendary=1)
        inactive = ScoringConfig.objects.create(
            is_active=False, threshold_rare=20, threshold_epic=10, threshold_legendary=1,
        )
        boundaries = [(0, 'legendary'), (1.99, 'legendary'), (2, 'epic'), (4.99, 'epic'),
                      (5, 'rare'), (14.99, 'rare'), (15, 'common'), (100, 'common')]
        for offset, (percent, _) in enumerate(boundaries):
            daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=offset), status='published')
            slot = DailySlot.objects.create(daily=daily, position=1, role='mid')
            game = Submission.objects.create(daily=daily, user=user, total_points=500-percent)
            SubmissionAnswer.objects.create(
                submission=game, daily_slot=slot, player=player, is_correct=True,
                rarity_percent=percent, rarity_tier='common', points_awarded=-percent,
                scoring_pick_count=1, scoring_sample_size=100,
            )
            AnswerStatsDaily.objects.create(
                daily_slot=slot, player=player, pick_percent=percent, pick_count=1, rarity_tier='common',
            )
        # The derived rarity counter excludes incomplete and practice games.
        incomplete_daily = Daily.objects.create(date=timezone.localdate()+timedelta(days=1))
        incomplete_slot = DailySlot.objects.create(daily=incomplete_daily, position=1, role='mid')
        DailySlot.objects.create(daily=incomplete_daily, position=2, role='top')
        for practice in [False, True]:
            game = Submission.objects.create(daily=incomplete_daily, user=user, is_practice=practice)
            SubmissionAnswer.objects.create(
                submission=game, daily_slot=incomplete_slot, player=player, is_correct=True,
                rarity_percent=0, rarity_tier='common', points_awarded=0,
            )
        stats = user.stats
        stats.games_played = len(boundaries)
        stats.total_points = sum(500-percent for percent, _ in boundaries)
        stats.avg_points = stats.total_points / len(boundaries)
        stats.best_score = 500
        stats.legendary_answers = 0
        stats.save()

        def preserved():
            return {
                'games': list(Submission.objects.order_by('pk').values()),
                'answers': [{key: value for key, value in row.items() if key != 'rarity_tier'}
                            for row in SubmissionAnswer.objects.order_by('pk').values()],
                'snapshots': [{key: value for key, value in row.items() if key != 'rarity_tier'}
                              for row in AnswerStatsDaily.objects.order_by('pk').values()],
                'stats': {key: value for key, value in type(stats).objects.filter(pk=stats.pk).values().get().items()
                          if key != 'legendary_answers'},
            }

        before = preserved()
        historical_apps = MigrationLoader(connection).project_state([
            ('scoring', '0004_display_rarity_thresholds'),
        ]).apps
        for _ in range(2):
            rarity_migration.update_display_rarity(historical_apps, SimpleNamespace(connection=connection))
            self.assertEqual(preserved(), before)
            self.assertEqual(list(AnswerStatsDaily.objects.order_by('pk').values_list('rarity_tier', flat=True)),
                             [tier for _, tier in boundaries])
            self.assertEqual(list(SubmissionAnswer.objects.order_by('pk').values_list('rarity_tier', flat=True)),
                             [tier for _, tier in boundaries] + ['legendary', 'legendary'])
            active.refresh_from_db()
            inactive.refresh_from_db()
            stats.refresh_from_db()
            self.assertEqual((active.threshold_rare, active.threshold_epic, active.threshold_legendary), (15, 5, 2))
            self.assertEqual((inactive.threshold_rare, inactive.threshold_epic, inactive.threshold_legendary), (20, 10, 1))
            self.assertEqual(stats.legendary_answers, 2)
