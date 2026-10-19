import importlib

from django.apps import apps
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import GuestProfile


class NicknameHistoryTests(TestCase):
    token = '9dcf4467-02d2-4b84-9630-e666f598dd89'

    def setUp(self):
        self.client = APIClient()

    def profile(self, **updates):
        response = self.client.post('/api/v1/guest/profile/', {'guest_token': self.token, **updates}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_result_prompt_is_only_for_someone_who_never_set_a_custom_nickname(self):
        self.assertFalse(self.profile()['has_custom_nickname'])
        self.assertFalse(self.profile(nickname='')['has_custom_nickname'])
        self.assertFalse(self.profile(supported_team='t1')['has_custom_nickname'])
        self.assertTrue(self.profile(nickname='Axword')['has_custom_nickname'])
        cleared = self.profile(nickname='')
        self.assertIsNone(cleared['nickname'])
        self.assertTrue(cleared['has_custom_nickname'])
        self.assertTrue(self.profile(supported_team=None)['has_custom_nickname'])

    def test_rejected_nickname_does_not_hide_the_first_nickname_prompt(self):
        self.profile()
        response = self.client.post('/api/v1/guest/profile/', {'guest_token': self.token, 'nickname': 'kurwa'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.profile()['has_custom_nickname'])

    def test_migration_remembers_existing_names_without_changing_profiles(self):
        one = GuestProfile.objects.create(guest_key='a' * 64, nickname='Existing')
        two = GuestProfile.objects.create(guest_key='b' * 64)
        remember = importlib.import_module('apps.users.migrations.0006_guestprofile_nickname_history').remember_existing_nicknames
        for _ in range(2):
            remember(apps, connection.schema_editor())
            one.refresh_from_db()
            two.refresh_from_db()
            self.assertTrue(one.has_custom_nickname)
            self.assertEqual(one.nickname, 'Existing')
            self.assertFalse(two.has_custom_nickname)
