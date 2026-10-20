from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer
from .guest_profiles import guest_display_name, guest_identity_key
from .models import GuestProfile


class PersonalizedLeaderboardTests(TestCase):
    url = '/api/v1/leaderboard/'
    token = 'leaderboard-current-guest-1234'

    def setUp(self):
        self.client = APIClient()
        self.today = Daily.objects.create(date=timezone.localdate(), status='published')
        self.yesterday = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='scored')

    def population(self, count=120):
        Submission.objects.bulk_create([
            Submission(daily=self.today, guest_token=f'leaderboard-population-{index:04}',
                       total_points=index, errors_used=MAX_ERRORS)
            for index in range(count)
        ])

    def post(self, **data):
        return self.client.post(self.url, data, format='json')

    def test_public_get_defaults_to_fifty_and_returns_full_population_ranks(self):
        self.population()
        with self.assertNumQueries(5):
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['limit'], 50)
        self.assertEqual(response.data['total_players'], 120)
        self.assertEqual(len(response.data['results']), 50)
        self.assertEqual([row['rank'] for row in response.data['results']], list(range(1, 51)))
        self.assertIsNone(response.data['current_player'])
        self.assertEqual(response.data['results'][0]['avg_points'], 0)

    def test_all_four_limits_work_for_public_get_and_post(self):
        self.population()
        for limit in [10, 25, 50, 100]:
            with self.subTest(limit=limit):
                for response in [self.client.get(self.url, {'limit': limit}), self.post(limit=limit)]:
                    self.assertEqual(response.status_code, 200, response.data)
                    self.assertEqual(response.data['limit'], limit)
                    self.assertEqual(len(response.data['results']), limit)
                    self.assertEqual(response.data['total_players'], 120)
                    self.assertEqual(response.data['results'][-1]['rank'], limit)
        self.assertEqual(self.post().data['limit'], 50)

    def test_guest_beyond_top_hundred_still_gets_own_exact_global_rank(self):
        self.population()
        token = 'leaderboard-population-0115'
        response = self.post(guest_token=token, limit=10)
        self.assertEqual(response.status_code, 200)
        own = response.data['current_player']
        self.assertEqual(own['rank'], 116)
        self.assertEqual(own['avg_points'], 115)
        self.assertEqual(own['games_played'], 1)
        self.assertEqual(own['username'], guest_display_name(token))
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn(own, response.data['results'])
        for private in [token, guest_identity_key(token), 'guest_token', 'guest_key', 'user_id', '_identity']:
            self.assertNotIn(private, response.content.decode())

    def test_current_player_is_always_separate_even_when_in_visible_top(self):
        self.population(3)
        response = self.post(guest_token='leaderboard-population-0001')
        self.assertEqual(response.data['current_player'], response.data['results'][1])
        self.assertEqual(response.data['current_player']['rank'], 2)
        self.assertEqual(len(response.data['results']), 3)

    def test_duplicate_nicknames_and_tied_scores_do_not_merge_identities(self):
        tokens = ['leaderboard-duplicate-one', 'leaderboard-duplicate-two']
        for token in tokens:
            GuestProfile.objects.create(guest_key=guest_identity_key(token), nickname='Same')
            Submission.objects.create(daily=self.today, guest_token=token, total_points=10, errors_used=MAX_ERRORS)
        user = get_user_model().objects.create_user(username='Gość-Same')
        Submission.objects.create(daily=self.today, user=user, total_points=10, errors_used=MAX_ERRORS)
        ordered = sorted(tokens, key=guest_identity_key)
        for index, token in enumerate(ordered, 2):
            response = self.post(guest_token=token)
            own = response.data['current_player']
            self.assertEqual(response.data['total_players'], 3)
            self.assertEqual(own['rank'], index)
            self.assertEqual(own['username'], 'Gość-Same')
            self.assertTrue(own['is_guest'])
            self.assertFalse(response.data['results'][0]['is_guest'])
            self.assertEqual([row['rank'] for row in response.data['results']], [1, 2, 3])
            self.assertEqual(self.post(guest_token=token).data, response.data)

    def test_average_ties_use_best_score_then_more_games_before_nickname(self):
        third_day = Daily.objects.create(date=timezone.localdate() - timedelta(days=2), status='published')
        for token, name, scores in [
            ('leaderboard-tie-one', 'Alpha', [20]),
            ('leaderboard-tie-two', 'Beta', [10, 30]),
            ('leaderboard-tie-three', 'Zulu', [10, 20, 30]),
        ]:
            GuestProfile.objects.create(guest_key=guest_identity_key(token), nickname=name)
            for daily, score in zip([self.today, self.yesterday, third_day], scores):
                Submission.objects.create(daily=daily, guest_token=token, total_points=score, is_scored=True)
        rows = self.client.get(self.url).data['results']
        self.assertEqual([row['avg_points'] for row in rows], [20, 20, 20])
        self.assertEqual([row['best_score'] for row in rows], [10, 10, 20])
        self.assertEqual([row['games_played'] for row in rows], [3, 2, 1])
        self.assertEqual([row['username'] for row in rows], ['Gość-Zulu', 'Gość-Beta', 'Gość-Alpha'])

    def test_authenticated_identity_wins_over_body_guest_and_can_rank_beyond_hundred(self):
        self.population()
        user = get_user_model().objects.create_user(username='Registered')
        Submission.objects.create(daily=self.today, user=user, total_points=200, errors_used=MAX_ERRORS)
        self.client.force_authenticate(user)
        for response in [self.client.get(self.url), self.post(guest_token='leaderboard-population-0000', limit=100)]:
            self.assertEqual(response.status_code, 200)
            own = response.data['current_player']
            self.assertEqual(own['rank'], 121)
            self.assertEqual(own['username'], 'Registered')
            self.assertFalse(own['is_guest'])
            self.assertEqual(own['avg_points'], 200)
            self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_unranked_guest_uses_existing_name_without_creating_profile_or_game(self):
        profile = GuestProfile.objects.create(guest_key=guest_identity_key(self.token), nickname='Waiting')
        before = (GuestProfile.objects.count(), Submission.objects.count())
        response = self.post(guest_token=self.token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['current_player'], {
            'rank': None, 'username': 'Gość-Waiting', 'is_guest': True,
            'games_played': 0, 'total_points': 0, 'avg_points': None, 'best_score': None,
            'weighted_points': None,
            'diamond_picks': 0, 'legendary_answers': 0,
        })
        self.assertEqual(response.data['total_players'], 0)
        self.assertEqual((GuestProfile.objects.count(), Submission.objects.count()), before)
        profile.refresh_from_db()
        self.assertEqual(profile.nickname, 'Waiting')
        new_token = 'leaderboard-new-unranked-token'
        other = self.post(guest_token=new_token)
        self.assertEqual(other.data['current_player']['username'], guest_display_name(new_token))
        self.assertIsNone(other.data['current_player']['rank'])
        self.assertEqual(GuestProfile.objects.count(), before[0])

    def test_unranked_authenticated_player_has_null_rank_and_no_guest_profile(self):
        user = get_user_model().objects.create_user(username='Not played')
        self.client.force_authenticate(user)
        response = self.client.get(self.url)
        own = response.data['current_player']
        self.assertEqual(own['username'], 'Not played')
        self.assertFalse(own['is_guest'])
        self.assertIsNone(own['rank'])
        self.assertIsNone(own['avg_points'])
        self.assertIsNone(own['best_score'])
        self.assertEqual(own['games_played'], 0)
        self.assertEqual(GuestProfile.objects.count(), 0)

    def test_legacy_get_never_reads_guest_credentials_from_url(self):
        Submission.objects.create(daily=self.today, guest_token=self.token, total_points=10, errors_used=MAX_ERRORS)
        response = self.client.get(self.url, {'guest_token': self.token})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['current_player'])
        self.assertEqual(response.data['total_players'], 1)
        self.assertNotIn(self.token, response.content.decode())

    def test_invalid_limits_and_tokens_are_rejected_before_profile_or_game_creation(self):
        for value in [0, 1, 11, 20, 26, 51, 101, -10, 'bad', '050', '+50', '50.0', ' 50', 50.5, True, None, [], {}]:
            with self.subTest(limit=value):
                response = self.post(limit=value)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('limit', response.data)
        for value in ['20', 'bad', '050', '+50', '50.0', ' 50']:
            self.assertEqual(self.client.get(self.url, {'limit': value}).status_code, 400)
        for value in ['', 'short', 'x' * 65, 'contains spaces 1234', 123, None, ['secret']]:
            with self.subTest(token=value):
                response = self.post(guest_token=value)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('guest_token', response.data)
        self.assertEqual(GuestProfile.objects.count(), 0)
        self.assertEqual(Submission.objects.count(), 0)

    def test_daily_filter_keeps_own_rank_in_scope_and_archive_games_official(self):
        Submission.objects.create(daily=self.today, guest_token=self.token, total_points=200, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=self.yesterday, guest_token=self.token, total_points=5, is_scored=True)
        Submission.objects.create(daily=self.yesterday, guest_token='leaderboard-archive-other', total_points=10, is_scored=True)
        archived = self.post(guest_token=self.token, daily_id=self.yesterday.pk)
        self.assertEqual(archived.data['current_player']['rank'], 1)
        self.assertEqual(archived.data['current_player']['avg_points'], 5)
        self.assertEqual(archived.data['total_players'], 2)
        self.assertEqual(self.client.get(self.url, {'daily_id': self.yesterday.pk}).data['results'], archived.data['results'])
        global_response = self.post(guest_token=self.token)
        self.assertEqual(global_response.data['current_player']['rank'], 2)
        self.assertEqual(global_response.data['current_player']['avg_points'], 102.5)

    def test_unfinished_seed_practice_future_and_draft_do_not_rank_current_player(self):
        future = Daily.objects.create(date=timezone.localdate() + timedelta(days=1), status='published')
        draft = Daily.objects.create(date=timezone.localdate() - timedelta(days=2), status='draft')
        slot = DailySlot.objects.create(daily=self.today, position=1, role='top')
        DailySlot.objects.create(daily=self.today, position=2, role='mid')
        player = Player.objects.create(slug='pending-top', nickname='Top', primary_role='top')
        pending = Submission.objects.create(daily=self.today, guest_token=self.token, total_points=0)
        SubmissionAnswer.objects.create(submission=pending, daily_slot=slot, player=player, is_correct=True)
        Submission.objects.create(daily=self.today, guest_token=self.token, total_points=0, is_practice=True, is_scored=True)
        Submission.objects.create(daily=self.yesterday, guest_token=self.token, total_points=0, is_seed=True, is_scored=True)
        for daily in [future, draft]:
            Submission.objects.create(daily=daily, guest_token=self.token, total_points=0, is_scored=True)
            self.assertEqual(self.post(guest_token=self.token, daily_id=daily.pk).status_code, 404)
            self.assertEqual(self.client.get(self.url, {'daily_id': daily.pk}).status_code, 404)
        response = self.post(guest_token=self.token)
        self.assertEqual(response.data['results'], [])
        self.assertEqual(response.data['total_players'], 0)
        self.assertIsNone(response.data['current_player']['rank'])
        self.assertEqual(response.data['current_player']['games_played'], 0)
        self.assertEqual(self.post(guest_token=self.token, daily_id=self.yesterday.pk).data['total_players'], 0)
        self.assertEqual(self.post(daily_id='bad').status_code, 400)
        self.assertEqual(self.post(daily_id=999999).status_code, 404)
