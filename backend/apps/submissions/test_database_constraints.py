from datetime import date, timedelta
from importlib import import_module
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from apps.scoring.models import AnswerStatsDaily, ScoringConfig
from apps.users.models import UserStats
from .models import Submission, SubmissionAnswer, SubmissionAttempt


class DatabaseConstraintTests(TestCase):
    def setUp(self):
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slot = DailySlot.objects.create(daily=self.daily, position=1, role='top')
        self.second_slot = DailySlot.objects.create(daily=self.daily, position=2, role='mid')
        self.player = Player.objects.create(slug='player', nickname='Player', primary_role='top')
        self.game = Submission.objects.create(daily=self.daily, guest_token='guest')

    def rejected_update(self, queryset, **values):
        with self.assertRaises(IntegrityError), transaction.atomic():
            queryset.update(**values)

    def test_score_error_boundaries_and_nonfinite_values_are_enforced_on_raw_updates(self):
        rows = Submission.objects.filter(pk=self.game.pk)
        for value in [-0.1, 500.01, float('nan'), float('inf'), -float('inf')]:
            with self.subTest(score=value):
                self.rejected_update(rows, total_points=value)
        for errors in [-1, 11]:
            with self.subTest(errors=errors):
                self.rejected_update(rows, errors_used=errors)
        for score, errors in [(0, 0), (500, 10), (432.125, 4)]:
            rows.update(total_points=score, errors_used=errors)
            self.game.refresh_from_db()
            self.assertEqual((self.game.total_points, self.game.errors_used), (score, errors))

    def test_identity_is_exclusive_and_guest_token_cannot_be_empty_or_whitespace(self):
        user = get_user_model().objects.create_user(username='identity')
        for values in [dict(user=None, guest_token=None), dict(user=user, guest_token='both'),
                       dict(user=user, guest_token=''), dict(user=None, guest_token=''),
                       dict(user=None, guest_token=' \t\n ')]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                Submission.objects.create(daily=self.daily, **values)
        registered = Submission.objects.create(daily=self.daily, user=user)
        with self.assertRaises(ProtectedError):
            user.delete()
        self.assertTrue(Submission.objects.filter(pk=registered.pk).exists())

    def test_seed_is_guest_only_and_official_but_legacy_colliding_practice_is_preserved(self):
        user = get_user_model().objects.create_user(username='seed-not-user')
        for values in [dict(user=user), dict(guest_token='practice-seed', is_practice=True)]:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                Submission.objects.create(daily=self.daily, is_seed=True, **values)
        seed = Submission.objects.create(daily=self.daily, guest_token='seed', is_seed=True)
        legacy = Submission.objects.create(daily=self.daily, guest_token=self.game.guest_token, is_practice=True)
        self.assertFalse(seed.is_practice)
        self.assertNotEqual(legacy.pk, self.game.pk)

    def test_answer_deductions_percentages_and_sample_counts_reject_invalid_values(self):
        answer = SubmissionAnswer.objects.create(submission=self.game, daily_slot=self.slot,
                                                player=self.player, is_correct=True)
        rows = SubmissionAnswer.objects.filter(pk=answer.pk)
        for value in [0.1, -100.01, float('nan'), float('inf'), -float('inf')]:
            with self.subTest(points=value):
                self.rejected_update(rows, points_awarded=value)
        for value in [-0.01, 100.01, float('nan'), float('inf'), -float('inf')]:
            with self.subTest(percent=value):
                self.rejected_update(rows, rarity_percent=value)
        self.rejected_update(rows, scoring_pick_count=2, scoring_sample_size=1)
        self.rejected_update(rows, scoring_pick_count=-1)
        self.rejected_update(rows, scoring_sample_size=-1)
        rows.update(points_awarded=-100, rarity_percent=100, scoring_pick_count=3, scoring_sample_size=3)
        self.rejected_update(rows, is_correct=False)
        rows.update(is_correct=False, points_awarded=0, rarity_percent=None, scoring_pick_count=0, scoring_sample_size=0)
        answer.refresh_from_db()
        self.assertFalse(answer.is_correct)

    def test_correct_player_is_unique_but_wrong_answers_and_attempt_history_can_repeat(self):
        first = SubmissionAnswer.objects.create(submission=self.game, daily_slot=self.slot,
                                               player=self.player, is_correct=True)
        second = SubmissionAnswer.objects.create(submission=self.game, daily_slot=self.second_slot,
                                                player=self.player, is_correct=False)
        self.rejected_update(SubmissionAnswer.objects.filter(pk=second.pk), is_correct=True)
        for _ in range(2):
            SubmissionAttempt.objects.create(submission=self.game, daily_slot=self.second_slot,
                                             player=self.player, is_correct=False)
        self.assertEqual(self.game.answers.count(), 2)
        self.assertEqual(self.game.attempts.count(), 2)
        self.assertTrue(SubmissionAnswer.objects.get(pk=first.pk).is_correct)

    def test_snapshot_ranges_and_ordered_thresholds_are_checked_in_the_database(self):
        snapshot = AnswerStatsDaily.objects.create(daily_slot=self.slot, player=self.player,
                                                  pick_count=1, pick_percent=100, rarity_tier='common')
        rows = AnswerStatsDaily.objects.filter(pk=snapshot.pk)
        self.rejected_update(rows, pick_count=-1)
        for value in [-1, 101, float('nan'), float('inf'), -float('inf')]:
            with self.subTest(percent=value):
                self.rejected_update(rows, pick_percent=value)
        config = ScoringConfig.objects.create()
        config_rows = ScoringConfig.objects.filter(pk=config.pk)
        for values in [dict(threshold_legendary=-1), dict(threshold_epic=21), dict(threshold_rare=101),
                       dict(threshold_rare=26), dict(threshold_uncommon=14), dict(threshold_uncommon=101),
                       dict(threshold_uncommon=float('nan')), dict(threshold_uncommon=float('inf')),
                       dict(threshold_rare=float('nan')), dict(threshold_epic=float('inf')),
                       dict(threshold_legendary=float('nan'))]:
            with self.subTest(values=values):
                self.rejected_update(config_rows, **values)

    def test_aggregate_user_stats_are_nonnegative_finite_and_bounded_by_finished_games(self):
        user = get_user_model().objects.create_user(username='stats')
        rows = UserStats.objects.filter(user=user)
        rows.update(games_played=2, total_points=750.5, avg_points=375.25, best_score=500,
                    current_streak=1, max_streak=2)
        for values in [dict(games_played=-1), dict(legendary_answers=-1), dict(diamond_picks=-1),
                       dict(total_points=-1), dict(total_points=1000.01), dict(total_points=float('nan')),
                       dict(total_points=float('inf')), dict(avg_points=500.01), dict(avg_points=float('nan')),
                       dict(best_score=501), dict(best_score=-float('inf')),
                       dict(current_streak=3), dict(max_streak=3), dict(current_streak=-1)]:
            with self.subTest(values=values):
                self.rejected_update(rows, **values)

    def test_answer_and_bulk_services_reject_slots_from_another_daily_before_writing(self):
        other = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='scored')
        foreign_slot = DailySlot.objects.create(daily=other, position=1, role='top')
        DailySlotCondition.objects.create(slot=foreign_slot, condition_type='country', value='KR')
        client = APIClient()
        for path, payload in [('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk, 'slot_id': foreign_slot.pk,
            'player_slug': self.player.slug, 'guest_token': 'cross-daily',
        }), ('/api/v1/submissions/', {
            'daily_id': self.daily.pk, 'guest_token': 'cross-daily',
            'answers': [{'slot_id': foreign_slot.pk, 'player_slug': self.player.slug}],
        })]:
            with self.subTest(path=path):
                self.assertEqual(client.post(path, payload, format='json').status_code, 400)
                self.assertFalse(Submission.objects.filter(guest_token='cross-daily').exists())
                self.assertFalse(SubmissionAnswer.objects.exists())
                self.assertFalse(SubmissionAttempt.objects.exists())


class IntegrityMigrationTests(TransactionTestCase):
    before = [('submissions', '0004_percentage_scoring'), ('scoring', '0002_percentage_scoring'),
              ('users', '0002_preserve_fractional_scores'),
              ('players', '0002_alter_player_continent_alter_player_country_code_and_more'),
              ('dailies', '0008_daily_integrity_constraints')]

    def setUp(self):
        executor = MigrationExecutor(connection)
        self.latest = executor.loader.graph.leaf_nodes()
        executor.migrate(self.before)
        self.old_apps = executor.loader.project_state(self.before).apps

    def tearDown(self):
        MigrationExecutor(connection).migrate(self.latest)
        super().tearDown()

    def old_rows(self):
        DailyOld = self.old_apps.get_model('dailies', 'Daily')
        SlotOld = self.old_apps.get_model('dailies', 'DailySlot')
        PlayerOld = self.old_apps.get_model('players', 'Player')
        GameOld = self.old_apps.get_model('submissions', 'Submission')
        AnswerOld = self.old_apps.get_model('submissions', 'SubmissionAnswer')
        AttemptOld = self.old_apps.get_model('submissions', 'SubmissionAttempt')
        # Outside the immutable October release, which is replayed together with
        # the historical player migration during this real forward migration.
        board = DailyOld.objects.create(date=date(2040, 1, 1), status='published')
        first = SlotOld.objects.create(daily=board, position=1, role='top')
        second = SlotOld.objects.create(daily=board, position=2, role='mid')
        player = PlayerOld.objects.create(slug='historic', nickname='Historic')
        official = GameOld.objects.create(daily=board, guest_token='same', total_points=400)
        legacy = GameOld.objects.create(daily=board, guest_token='same', is_practice=True, total_points=500)
        correct = AnswerOld.objects.create(submission=official, daily_slot=first, player=player, is_correct=True,
                                           points_awarded=-100, rarity_percent=100)
        wrong = AnswerOld.objects.create(submission=official, daily_slot=second, player=player, is_correct=False)
        attempt = AttemptOld.objects.create(submission=official, daily_slot=second, player=player, is_correct=False)
        return official, legacy, correct, wrong, attempt

    def test_existing_wrong_history_and_colliding_legacy_practice_survive_forward_migration(self):
        official, legacy, correct, wrong, attempt = self.old_rows()
        MigrationExecutor(connection).migrate(self.latest)
        self.assertTrue(Submission.objects.get(pk=legacy.pk).is_practice)
        self.assertEqual(Submission.objects.get(pk=official.pk).total_points, 400)
        answer_ids = set(SubmissionAnswer.objects.filter(submission_id=official.pk).values_list('pk', flat=True))
        self.assertEqual(answer_ids, {correct.pk, wrong.pk})
        self.assertFalse(SubmissionAnswer.objects.get(pk=wrong.pk).is_correct)
        self.assertTrue(SubmissionAttempt.objects.filter(pk=attempt.pk, is_correct=False).exists())

    def test_preflight_reports_bad_historical_ids_and_never_repairs_them_silently(self):
        official, _legacy, _correct, _wrong, _attempt = self.old_rows()
        GameOld = self.old_apps.get_model('submissions', 'Submission')
        GameOld.objects.filter(pk=official.pk).update(errors_used=11)
        migration = import_module('apps.submissions.migrations.0005_integrity_constraints')
        with self.assertRaisesRegex(RuntimeError, 'errors: invalid existing IDs'):
            migration.validate_existing_rows(self.old_apps, SimpleNamespace(connection=connection))
        self.assertEqual(GameOld.objects.get(pk=official.pk).errors_used, 11)
        GameOld.objects.filter(pk=official.pk).update(errors_used=0)
