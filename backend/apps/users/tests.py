from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer
from .services import refresh_user_stats


class UserPrivacyAndStatsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username='player', email='private@example.test', first_name='Private')

    def test_user_details_are_visible_only_to_the_owner(self):
        url = f'/api/v1/users/{self.user.pk}/'
        self.assertIn(self.client.get(url).status_code, [401, 403])
        self.client.force_authenticate(get_user_model().objects.create_user(username='other'))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url).data['email'], self.user.email)

    def test_finishing_game_updates_stats_once(self):
        self.client.force_authenticate(self.user)
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR', label_pl='Korea', label_en='Korea')
        player = Player.objects.create(slug='top', nickname='Top', primary_role='top')
        payload = {'daily_id': daily.pk, 'slot_id': slot.pk, 'player_slug': player.slug}
        first = self.client.post('/api/v1/submissions/answer/', payload, format='json')
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.data['is_over'])
        self.client.post('/api/v1/submissions/answer/', payload, format='json')
        result = self.client.get('/api/v1/users/me/stats/')
        self.assertEqual(result.data['games_played'], 1)
        self.assertEqual(result.data['total_points'], first.data['total_points'])
        self.assertEqual(result.data['diamond_picks'], 0)

    def test_in_progress_games_do_not_inflate_stats_or_leaderboard(self):
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        DailySlot.objects.create(daily=daily, position=1, role='top')
        Submission.objects.create(daily=daily, user=self.user, total_points=90)
        self.client.force_authenticate(self.user)
        result = self.client.get('/api/v1/users/me/stats/')
        self.assertEqual(result.data['games_played'], 0)
        leaderboard = self.client.get('/api/v1/leaderboard/')
        self.assertEqual(leaderboard.data['results'], [])

    def test_stats_preserve_fractions_and_streaks_skip_archive_practice(self):
        today = timezone.localdate()
        for days_ago, points in [(7, 10.5), (6, 20.25), (5, 30.0), (1, 8.75)]:
            daily = Daily.objects.create(date=today - timedelta(days=days_ago), status='scored')
            Submission.objects.create(daily=daily, user=self.user, total_points=points, is_scored=True)
        practice_daily = Daily.objects.get(date=today - timedelta(days=5))
        Submission.objects.create(daily=practice_daily, user=self.user, total_points=120,
                                  is_scored=True, is_practice=True)
        for _ in range(2):
            result = refresh_user_stats(self.user.pk)
            self.assertEqual(result.games_played, 4)
            self.assertEqual(result.total_points, 69.5)
            self.assertEqual(result.avg_points, 17.375)
            self.assertEqual(result.best_score, 30)
            self.assertEqual(result.current_streak, 1)
            self.assertEqual(result.max_streak, 3)
        leaderboard = self.client.get('/api/v1/leaderboard/')
        self.assertEqual(leaderboard.data['results'][0]['total_points'], 69.5)

    def test_current_streak_expires_without_play_yesterday_or_today(self):
        daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=2), status='scored')
        Submission.objects.create(daily=daily, user=self.user, is_scored=True)
        result = refresh_user_stats(self.user.pk)
        self.assertEqual(result.current_streak, 0)
        self.assertEqual(result.max_streak, 1)


class LeaderboardTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.today = Daily.objects.create(date=timezone.localdate(), status='published')
        self.yesterday = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='scored')

    def test_global_guests_aggregate_float_scores_without_exposing_tokens(self):
        secret_token = 'private-guest-identity-never-public'
        Submission.objects.create(daily=self.today, guest_token=secret_token, total_points=10.25, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=self.yesterday, guest_token=secret_token, total_points=20.5, is_scored=True)
        Submission.objects.create(daily=self.yesterday, guest_token=secret_token, total_points=120, is_scored=True, is_practice=True)
        response = self.client.get('/api/v1/leaderboard/')
        entry = response.data['results'][0]
        self.assertTrue(entry['is_guest'])
        self.assertRegex(entry['username'], r'^Gość-[A-F0-9]{8}$')
        self.assertEqual(entry['total_points'], 30.75)
        self.assertEqual(entry['best_score'], 20.5)
        self.assertEqual(entry['games_played'], 2)
        self.assertNotIn(secret_token, response.content.decode())
        self.assertNotIn('guest_token', response.content.decode())
        again = self.client.get('/api/v1/leaderboard/')
        self.assertEqual(again.data, response.data)

    def test_daily_filter_preserves_user_and_guest_identity_and_excludes_other_days(self):
        user = get_user_model().objects.create_user(username='registered')
        Submission.objects.create(daily=self.today, user=user, total_points=15.5, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=self.today, guest_token='guest', total_points=10.25, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=self.yesterday, user=user, total_points=90, is_scored=True)
        global_rows = self.client.get('/api/v1/leaderboard/').data['results']
        daily_rows = self.client.get('/api/v1/leaderboard/', {'daily_id': self.today.pk}).data['results']
        self.assertEqual([row['total_points'] for row in global_rows], [105.5, 10.25])
        self.assertEqual([row['total_points'] for row in daily_rows], [15.5, 10.25])
        self.assertEqual(daily_rows[0]['username'], 'registered')
        self.assertFalse(daily_rows[0]['is_guest'])
        self.assertEqual(global_rows[1]['username'], daily_rows[1]['username'])

    def test_in_progress_and_unavailable_games_do_not_enter_ranking(self):
        Submission.objects.create(daily=self.today, guest_token='pending', total_points=500)
        future = Daily.objects.create(date=timezone.localdate() + timedelta(days=1), status='published')
        draft = Daily.objects.create(date=timezone.localdate() - timedelta(days=2), status='draft')
        for daily in [future, draft]:
            Submission.objects.create(daily=daily, guest_token='not-public', total_points=499, is_scored=True)
            self.assertEqual(self.client.get('/api/v1/leaderboard/', {'daily_id': daily.pk}).status_code, 404)
        self.assertEqual(self.client.get('/api/v1/leaderboard/').data['results'], [])
        self.assertEqual(self.client.get('/api/v1/leaderboard/', {'daily_id': 999999}).status_code, 404)
        self.assertEqual(self.client.get('/api/v1/leaderboard/', {'daily_id': 'bad'}).status_code, 400)

    def test_finished_unscored_answers_count_once_and_ties_are_deterministic(self):
        slot = DailySlot.objects.create(daily=self.today, position=1, role='top')
        second_slot = DailySlot.objects.create(daily=self.today, position=2, role='mid')
        player = Player.objects.create(slug='top', nickname='Top', primary_role='top')
        mid = Player.objects.create(slug='mid', nickname='Mid', primary_role='mid')
        for token in ['token-b', 'token-a']:
            sub = Submission.objects.create(daily=self.today, guest_token=token, total_points=15.5)
            for daily_slot, picked in [(slot, player), (second_slot, mid)]:
                SubmissionAnswer.objects.create(submission=sub, daily_slot=daily_slot, player=picked,
                                                 is_correct=True, rarity_tier='legendary')
        incomplete = Submission.objects.create(daily=self.today, guest_token='incomplete', total_points=498)
        SubmissionAnswer.objects.create(submission=incomplete, daily_slot=slot, player=player, is_correct=True)
        rows = self.client.get('/api/v1/leaderboard/').data['results']
        self.assertEqual(len(rows), 2)
        self.assertEqual([row['total_points'] for row in rows], [15.5, 15.5])
        self.assertEqual([row['legendary_answers'] for row in rows], [2, 2])
        self.assertEqual([row['username'] for row in rows], sorted(row['username'] for row in rows))
