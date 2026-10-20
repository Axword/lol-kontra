from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from .guest_profiles import guest_identity_key
from .models import GuestProfile


class ProfileAccessPreviewTests(TestCase):
    token = 'private-transfer-test-12345'
    url = '/api/v1/guest/profile/preview/'

    def setUp(self):
        self.client = APIClient()
        self.profile = GuestProfile.objects.create(guest_key=guest_identity_key(self.token), nickname='Player',
                                                   has_custom_nickname=True, supported_team='t1')
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slot = DailySlot.objects.create(daily=self.daily, position=1, role='top')
        self.player = Player.objects.create(slug='transfer-player', nickname='TransferPlayer', primary_role='top')
        self.game = Submission.objects.create(daily=self.daily, guest_token=self.token, total_points=8.25)
        SubmissionAnswer.objects.create(submission=self.game, daily_slot=self.slot, player=self.player,
                                         is_correct=True, rarity_percent=8.25, is_diamond_pick=True)

    def test_preview_keeps_exact_history_and_returns_only_server_stats(self):
        models = (Daily, DailySlot, Player, Submission, SubmissionAnswer, SubmissionAttempt, GuestProfile)
        before = {model: list(model.objects.order_by('pk').values()) for model in models}
        response = self.client.post(self.url, {'guest_token': self.token, 'nickname': 'Spoofed',
                                             'total_points': -999, 'supported_team': 'g2'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['nickname'], 'Player')
        self.assertEqual(response.data['supported_team']['id'], 't1')
        self.assertEqual(response.data['stats']['games_played'], 1)
        self.assertEqual(response.data['stats']['total_points'], 8.25)
        self.assertEqual(response.data['stats']['diamond_picks'], 1)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn(self.token, response.content.decode())
        self.assertNotIn(guest_identity_key(self.token), response.content.decode())
        for model, values in before.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), values)

    def test_missing_identity_is_not_created(self):
        response = self.client.post(self.url, {'guest_token': 'unknown-credential-56789'}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(GuestProfile.objects.count(), 1)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_legacy_games_without_a_profile_still_resolve_without_creating_one(self):
        self.profile.delete()
        response = self.client.post(self.url, {'guest_token': self.token}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['stats']['games_played'], 1)
        self.assertFalse(GuestProfile.objects.exists())

    def test_nickname_only_profile_transfers_without_requiring_a_finished_game(self):
        self.game.delete()
        response = self.client.post(self.url, {'guest_token': self.token}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['nickname'], 'Player')
        self.assertEqual(response.data['stats']['games_played'], 0)

    def test_no_query_string_identity_and_bad_credentials_are_rejected(self):
        self.assertEqual(self.client.get(self.url, {'guest_token': self.token}).status_code, 405)
        for value in ('short', 'x' * 65, 'x' * 20 + '\n', ['x' * 20], None, 1234567890123456789):
            response = self.client.post(self.url, {'guest_token': value}, format='json')
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_synthetic_only_identity_does_not_become_a_real_profile(self):
        self.profile.delete()
        self.game.is_seed = True
        self.game.save(update_fields=['is_seed'])
        response = self.client.post(self.url, {'guest_token': self.token}, format='json')
        self.assertEqual(response.status_code, 404)
