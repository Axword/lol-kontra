from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer
from .engine import score_daily, tier_for_percent
from .models import AnswerStatsDaily, ScoringConfig
from .tasks import nightly_scoring


class ScoringTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='closed')
        self.slot = DailySlot.objects.create(daily=self.daily, position=1, role='top')
        self.player = Player.objects.create(slug='top', nickname='Top', primary_role='top')
        self.cfg = ScoringConfig.objects.create()

    def test_tier_boundaries(self):
        for percent, expected in [(0, 'legendary'), (1.99, 'legendary'), (2, 'epic'),
                                  (4.99, 'epic'), (5, 'rare'), (14.99, 'rare'),
                                  (15, 'common'), (100, 'common')]:
            with self.subTest(percent=percent):
                self.assertEqual(tier_for_percent(percent, self.cfg), expected)

    def test_final_scoring_is_idempotent_and_excludes_wrong_answers(self):
        first = Submission.objects.create(daily=self.daily, guest_token='one')
        second = Submission.objects.create(daily=self.daily, guest_token='two')
        diamond = SubmissionAnswer.objects.create(submission=first, daily_slot=self.slot, player=self.player,
                                                   is_correct=True, is_diamond_pick=True)
        wrong = SubmissionAnswer.objects.create(submission=second, daily_slot=self.slot, player=self.player,
                                                 is_correct=False, points_awarded=0)
        for _ in range(2):
            score_daily(self.daily.pk)
            diamond.refresh_from_db()
            wrong.refresh_from_db()
            first.refresh_from_db()
            self.assertEqual(diamond.points_awarded, -100)
            self.assertFalse(diamond.is_diamond_pick)
            self.assertEqual(wrong.points_awarded, 0)
            self.assertEqual(first.total_points, 400)
            self.assertTrue(first.is_scored)
            self.assertEqual(AnswerStatsDaily.objects.get().pick_count, 1)

    def test_invalid_score_filters_return_400_instead_of_500(self):
        url = f'/api/v1/dailies/{self.daily.pk}/score-distribution/'
        for value in ['abc', 'NaN', 'Infinity', '-Infinity', '-1', '501']:
            with self.subTest(value=value):
                response = self.client.get(url, {'user_score': value})
                self.assertEqual(response.status_code, 400)

    def test_distribution_handles_ties_and_zero_standard_deviation(self):
        for token in ['one', 'two']:
            Submission.objects.create(daily=self.daily, guest_token=token, total_points=60, is_scored=True)
        response = self.client.get(f'/api/v1/dailies/{self.daily.pk}/score-distribution/', {'user_score': 60})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['rank'], 1)
        self.assertEqual(response.data['stddev'], 0)
        self.assertEqual(response.data['distribution'], [{'score': 60, 'count': 2}])

    def test_unknown_or_unpublished_daily_stats_are_not_public(self):
        for suffix in ['answer-stats', 'score-distribution']:
            self.assertEqual(self.client.get(f'/api/v1/dailies/999999/{suffix}/').status_code, 404)
            self.daily.status = 'draft'
            self.daily.save()
            self.assertEqual(self.client.get(f'/api/v1/dailies/{self.daily.pk}/{suffix}/').status_code, 404)

    def test_nightly_scoring_leaves_today_open_and_closes_yesterday(self):
        today = Daily.objects.create(date=timezone.localdate(), status='published')
        self.daily.status = 'published'
        self.daily.save()
        nightly_scoring()
        today.refresh_from_db()
        self.daily.refresh_from_db()
        self.assertEqual(today.status, 'published')
        self.assertEqual(self.daily.status, 'scored')
        self.assertIsNotNone(self.daily.closed_at)

    def test_nightly_scoring_does_not_publish_draft(self):
        self.daily.status = 'draft'
        self.daily.save()
        nightly_scoring()
        self.daily.refresh_from_db()
        self.assertEqual(self.daily.status, 'draft')

    def test_final_scoring_rebuilds_registered_user_statistics(self):
        user = get_user_model().objects.create_user(username='scored-user')
        sub = Submission.objects.create(daily=self.daily, user=user, errors_used=MAX_ERRORS)
        SubmissionAnswer.objects.create(submission=sub, daily_slot=self.slot, player=self.player, is_correct=True)
        score_daily(self.daily.pk)
        score_daily(self.daily.pk)
        user.stats.refresh_from_db()
        self.assertEqual(user.stats.games_played, 1)
        self.assertEqual(user.stats.total_points, 400)
        self.assertEqual(user.stats.best_score, 400)

    def test_scoring_failure_rolls_back_partial_results(self):
        sub = Submission.objects.create(daily=self.daily, guest_token='one')
        answer = SubmissionAnswer.objects.create(submission=sub, daily_slot=self.slot, player=self.player, is_correct=True)
        with patch('apps.scoring.engine.recalc_submission_total', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                score_daily(self.daily.pk)
        answer.refresh_from_db()
        self.assertEqual(answer.points_awarded, 0)
        self.assertFalse(AnswerStatsDaily.objects.exists())

    def test_finished_archive_game_updates_official_distribution_and_user_stats(self):
        official = Submission.objects.create(daily=self.daily, guest_token='official')
        SubmissionAnswer.objects.create(submission=official, daily_slot=self.slot, player=self.player, is_correct=True)
        score_daily(self.daily.pk)
        self.daily.status = 'scored'
        self.daily.save()
        DailySlotCondition.objects.create(slot=self.slot, condition_type='country', value='KR', label_pl='Korea', label_en='Korea')
        other = Player.objects.create(slug='other-top', nickname='Other', primary_role='top')
        user = get_user_model().objects.create_user(username='practice-user')
        self.client.force_authenticate(user)
        result = self.client.post('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk, 'slot_id': self.slot.pk, 'player_slug': other.slug,
        }, format='json')
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data['is_practice'])
        self.assertTrue(result.data['is_scored'])
        self.assertEqual(result.data['rarity_tier'], 'legendary')
        self.assertEqual(result.data['total_points'], 500)
        official.refresh_from_db()
        self.assertEqual(official.total_points, 400)
        self.assertEqual(AnswerStatsDaily.objects.count(), 1)
        distribution = self.client.get(f'/api/v1/dailies/{self.daily.pk}/score-distribution/')
        self.assertEqual(distribution.data['total_submissions'], 2)
        self.assertEqual(distribution.data['distribution'], [{'score': 400, 'count': 1}, {'score': 500, 'count': 1}])
        user.stats.refresh_from_db()
        self.assertEqual(user.stats.games_played, 1)

    def test_empty_official_population_has_zero_initial_deduction_and_idempotent_retry(self):
        DailySlotCondition.objects.create(slot=self.slot, condition_type='country', value='KR', label_pl='Korea', label_en='Korea')
        DailySlot.objects.create(daily=self.daily, position=2, role='mid')
        for status in ['published', 'scored']:
            with self.subTest(status=status):
                self.daily.status = status
                self.daily.save(update_fields=['status'])
                Submission.objects.all().delete()
                payload = {'daily_id': self.daily.pk, 'slot_id': self.slot.pk,
                           'player_slug': self.player.slug, 'guest_token': f'practice-{status}'}
                first = self.client.post('/api/v1/submissions/answer/', payload, format='json')
                self.assertEqual(first.status_code, 200)
                for result in [first, self.client.post('/api/v1/submissions/answer/', payload, format='json')]:
                    self.assertFalse(result.data['is_practice'])
                    self.assertTrue(result.data['is_provisional'])
                    self.assertEqual(result.data['sample_size'], 0)
                    self.assertEqual(result.data['pick_count'], 0)
                    self.assertEqual(result.data['pick_percent'], 0)
                    self.assertEqual(result.data['rarity_percent'], 0)
                    self.assertEqual(result.data['answers'][0]['rarity_percent'], 0)
                    self.assertEqual(result.data['deduction'], 0)
                    self.assertEqual(result.data['total_points'], 500)
                answer = SubmissionAnswer.objects.get(submission_id=first.data['submission_id'])
                self.assertEqual(answer.rarity_percent, 0)
                self.assertFalse(answer.is_diamond_pick)
                self.assertIsNone(answer.diamond_awarded_at)
                self.assertEqual(answer.submission.attempts.count(), 1)
        score_daily(self.daily.pk)
        self.assertEqual(AnswerStatsDaily.objects.get().pick_percent, 100)
