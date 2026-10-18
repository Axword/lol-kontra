from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt
from .guest_profiles import guest_identity_key
from .models import GuestProfile


class GuestProfileTests(TestCase):
    token = '5d816a73-9be6-41b6-a527-dd08e480df30'
    other_token = '3a36ae26-d844-471f-a17f-449135bc4c2f'
    url = '/api/v1/guest/profile/'

    def setUp(self):
        self.client = APIClient()
        self.today = Daily.objects.create(date=timezone.localdate(), status='published')

    def post(self, nickname=None, **kwargs):
        payload = {'guest_token': self.token, **kwargs}
        if nickname is not None:
            payload['nickname'] = nickname
        return self.client.post(self.url, payload, format='json')

    def test_default_name_is_stable_private_and_does_not_create_game_data(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['nickname'])
        self.assertRegex(response.data['display_name'], r'^Gość-[A-F0-9]{8}$')
        self.assertEqual(response.data['stats']['games_played'], 0)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertEqual(self.post().data, response.data)
        profile = GuestProfile.objects.get()
        self.assertEqual(profile.guest_key, guest_identity_key(self.token))
        self.assertNotIn(self.token, profile.guest_key)
        self.assertNotIn(self.token, response.content.decode())
        self.assertNotIn(profile.guest_key, response.content.decode())
        self.assertEqual(Submission.objects.count(), 0)
        self.assertEqual(SubmissionAnswer.objects.count(), 0)
        self.assertEqual(SubmissionAttempt.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_custom_name_normalizes_and_can_be_loaded_or_reset(self):
        response = self.post('  Żółw   Ninja_7  ')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['nickname'], 'Żółw Ninja_7')
        self.assertEqual(response.data['display_name'], 'Gość-Żółw Ninja_7')
        self.assertEqual(self.post().data, response.data)
        self.assertEqual(self.post('   ').data['nickname'], None)
        self.assertRegex(self.post().data['display_name'], r'^Gość-[A-F0-9]{8}$')
        self.assertEqual(GuestProfile.objects.count(), 1)

    def test_unicode_names_and_innocent_substrings_are_accepted(self):
        for nickname in ['Scunthorpe', 'Sukienka', 'Dickinson', 'Sussex', 'Nigeria', 'Nigel', 'Żółw', 'Łukasz-99', 'Knight_22', 'Ｆａｋｅｒ', '민수123']:
            with self.subTest(nickname=nickname):
                response = self.post(nickname)
                self.assertEqual(response.status_code, 200, response.data)

    def test_offensive_words_and_common_obfuscation_are_rejected_without_changes(self):
        self.post('Original')
        for nickname in ['kurwa', 'KURW4', 'k u r w a', 'k_u_r_w_a', 'kurrwa', 'kurwa123',
                         'jebany', 'jebać', 'chuj', 'fuck', 'f u c k', 'f4gg0t', 'FUCK YOU',
                         'nigger', 'heilhitler', '  pIerDol  ', 'a shit name', 'kurwа']:
            with self.subTest(nickname=nickname):
                response = self.post(nickname)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('nickname', response.data)
                self.assertEqual(GuestProfile.objects.get().nickname, 'Original')

    def test_clear_severe_roots_cannot_be_hidden_inside_decorated_nicknames(self):
        for nickname in ['xxkurwaxx', 'FuckerFan', 'niggerking', 'XXN1GGG3RXX', 'NiggaKing',
                         'xxf4gg0txx', 'x x k_u_r_w_a x x', 'F u c k e r F a n', 'SuperPierdolKing', 'MegaSkurwiel']:
            with self.subTest(nickname=nickname):
                response = self.post(nickname)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('nickname', response.data)
        self.assertEqual(GuestProfile.objects.count(), 0)

    def test_invalid_nicknames_are_rejected_before_any_profile_is_created(self):
        for nickname in ['ab', 'A' * 25, '<script>', 'https://example.com', 'abc@example.com',
                         'hello\nworld', 'hello\tworld', 'abc\u200bdef', '\u202eFaker', '---', '🙂🙂🙂', 123, None, ['abc']]:
            with self.subTest(nickname=nickname):
                response = self.client.post(self.url, {'guest_token': self.token, 'nickname': nickname}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('nickname', response.data)
                self.assertEqual(GuestProfile.objects.count(), 0)

    def test_malformed_guest_token_is_rejected(self):
        for token in ['', 'short', 'a' * 65, 'x' * 16 + '\n', 'contains spaces 1234', 'https://evil.test/12345', 'a' * 15, 1234567890123456, None]:
            with self.subTest(token=token):
                response = self.client.post(self.url, {'guest_token': token, 'nickname': 'Knight'}, format='json')
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('guest_token', response.data)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(GuestProfile.objects.count(), 0)

    def test_equal_nicknames_never_merge_guest_identity_or_existing_progress(self):
        first = Submission.objects.create(daily=self.today, guest_token=self.token, total_points=321.5, errors_used=MAX_ERRORS)
        second = Submission.objects.create(daily=self.today, guest_token=self.other_token, total_points=110, errors_used=MAX_ERRORS)
        self.post('Player')
        self.post('Player', guest_token=self.other_token)
        self.assertEqual(GuestProfile.objects.count(), 2)
        self.assertEqual(self.post().data['stats']['total_points'], 321.5)
        self.assertEqual(self.post(guest_token=self.other_token).data['stats']['total_points'], 110)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.guest_token, first.total_points), (self.token, 321.5))
        self.assertEqual((second.guest_token, second.total_points), (self.other_token, 110))

    def test_stats_count_finished_real_public_games_only_and_preserve_fractions(self):
        yesterday = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='scored')
        older = Daily.objects.create(date=timezone.localdate() - timedelta(days=3), status='published')
        pending = Daily.objects.create(date=timezone.localdate() - timedelta(days=5), status='published')
        draft = Daily.objects.create(date=timezone.localdate() - timedelta(days=6), status='draft')
        seed_only = Daily.objects.create(date=timezone.localdate() - timedelta(days=7), status='scored')
        future = Daily.objects.create(date=timezone.localdate() + timedelta(days=1), status='published')
        Submission.objects.create(daily=self.today, guest_token=self.token, total_points=450.5, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=yesterday, guest_token=self.token, total_points=200.25, is_scored=True)
        finished = Submission.objects.create(daily=older, guest_token=self.token, total_points=300.5)
        slot = DailySlot.objects.create(daily=older, position=1, role='top')
        player = Player.objects.create(slug='top', nickname='Top', primary_role='top')
        SubmissionAnswer.objects.create(submission=finished, daily_slot=slot, player=player, is_correct=True,
                                        rarity_tier='legendary', is_diamond_pick=True)
        Submission.objects.create(daily=pending, guest_token=self.token, total_points=500)
        Submission.objects.create(daily=yesterday, guest_token=self.token, total_points=500, is_scored=True, is_practice=True)
        Submission.objects.create(daily=draft, guest_token=self.token, total_points=500, is_scored=True)
        Submission.objects.create(daily=future, guest_token=self.token, total_points=500, is_scored=True)
        Submission.objects.create(daily=seed_only, guest_token=self.token, total_points=500, is_seed=True, is_scored=True)
        Submission.objects.create(daily=self.today, guest_token=self.other_token, total_points=500, is_seed=True, is_scored=True)
        stats = self.post().data['stats']
        self.assertEqual(stats, {
            'games_played': 3, 'total_points': 951.25, 'avg_points': 951.25 / 3,
            'best_score': 450.5, 'legendary_answers': 1, 'diamond_picks': 1,
            'current_streak': 2, 'max_streak': 2,
        })

    def test_leaderboard_uses_custom_or_default_names_without_private_keys(self):
        user = get_user_model().objects.create_user(username='Registered')
        Submission.objects.create(daily=self.today, user=user, total_points=490, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=self.today, guest_token=self.token, total_points=400, errors_used=MAX_ERRORS)
        Submission.objects.create(daily=self.today, guest_token=self.other_token, total_points=300, errors_used=MAX_ERRORS)
        profile = self.post('Knight')
        response = self.client.get('/api/v1/leaderboard/')
        rows = response.data['results']
        self.assertEqual(rows[0]['username'], 'Registered')
        self.assertFalse(rows[0]['is_guest'])
        self.assertEqual(rows[1]['username'], profile.data['display_name'])
        self.assertRegex(rows[2]['username'], r'^Gość-[A-F0-9]{8}$')
        self.assertTrue(rows[1]['is_guest'])
        for private in [self.token, self.other_token, guest_identity_key(self.token), guest_identity_key(self.other_token), 'guest_token', 'guest_key']:
            self.assertNotIn(private, response.content.decode())
