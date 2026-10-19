from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from .guest_profiles import guest_identity_key
from .models import GuestProfile
from .worlds_teams import WORLDS_2026_TEAM_IDS, supported_team_details


class GuestSupporterTeamTests(TestCase):
    token = 'c55e82d9-2f3f-4a06-9c18-9a36b5a7f121'
    profile_url = '/api/v1/guest/profile/'

    def setUp(self):
        self.client = APIClient()

    def post(self, **updates):
        return self.client.post(self.profile_url, {
            'guest_token': self.token, **updates,
        }, format='json')

    def test_catalog_contains_all_nineteen_teams_and_local_badge_paths(self):
        response = self.client.get('/api/v1/guest/teams/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['season'], 2026)
        self.assertEqual(response.data['source_url'], 'https://lolesports.com/en-GB/news/worlds-2026-primer')
        teams = response.data['teams']
        self.assertEqual(len(teams), 19)
        self.assertEqual({team['id'] for team in teams}, {
            'al', 'blg', 'tes', 'ig', 'gen', 'hle', 't1', 'dk', 'g2', 'mkoi',
            'kc', 'tlaw', 'lyon', 'c9', 'tsw', 'cfo', 'mvk', 'los', 'fur',
        })
        for team in teams:
            self.assertEqual(set(team), {'id', 'code', 'name', 'region', 'logo_url'})
            self.assertEqual(team['logo_url'], f"/teams/worlds-2026/{team['id']}.png")
            self.assertTrue(all(team[key] for key in ('name', 'code', 'region')))
        self.assertEqual(GuestProfile.objects.count(), 0)

    def test_all_catalog_teams_can_be_saved_and_loaded(self):
        for team_id in WORLDS_2026_TEAM_IDS:
            with self.subTest(team_id=team_id):
                saved = self.post(supported_team=team_id)
                self.assertEqual(saved.status_code, 200, saved.data)
                self.assertEqual(saved.data['supported_team'], supported_team_details(team_id))
                self.assertEqual(self.post().data['supported_team'], saved.data['supported_team'])
                self.assertEqual(GuestProfile.objects.get().supported_team, team_id)
        self.assertEqual(GuestProfile.objects.count(), 1)

    def test_default_is_no_team_and_null_clears_a_saved_team(self):
        self.assertIsNone(self.post().data['supported_team'])
        self.post(supported_team='t1')
        response = self.post(supported_team=None)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data['supported_team'])
        self.assertIsNone(self.post().data['supported_team'])
        self.assertEqual(GuestProfile.objects.get().supported_team, '')

    def test_nickname_and_team_updates_preserve_each_other(self):
        initial = self.post(nickname='Axword', supported_team='g2')
        self.assertEqual(initial.status_code, 200)
        changed_name = self.post(nickname='Knight')
        self.assertEqual(changed_name.data['nickname'], 'Knight')
        self.assertEqual(changed_name.data['supported_team']['id'], 'g2')
        changed_team = self.post(supported_team='t1')
        self.assertEqual(changed_team.data['nickname'], 'Knight')
        self.assertEqual(changed_team.data['display_name'], 'Gość-Knight')
        self.assertEqual(changed_team.data['supported_team']['id'], 't1')
        cleared_name = self.post(nickname='')
        self.assertIsNone(cleared_name.data['nickname'])
        self.assertEqual(cleared_name.data['supported_team']['id'], 't1')
        self.assertRegex(cleared_name.data['display_name'], r'^Gość-[A-F0-9]{8}$')
        self.assertEqual(self.post(supported_team=None).data['nickname'], None)

    def test_invalid_team_does_not_create_a_profile(self):
        for value in ['', 'T1', 'unknown', ' t1', 't1 ', '<script>', 123, False, [], {'id': 't1'}]:
            with self.subTest(value=value):
                response = self.post(supported_team=value)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('supported_team', response.data)
                self.assertEqual(GuestProfile.objects.count(), 0)

    def test_invalid_combined_update_is_rejected_atomically(self):
        self.post(nickname='Original', supported_team='g2')
        for updates, invalid_field in [
            ({'nickname': 'Changed', 'supported_team': 'unknown'}, 'supported_team'),
            ({'nickname': 'fuck', 'supported_team': 't1'}, 'nickname'),
            ({'nickname': 'fuck', 'supported_team': None}, 'nickname'),
        ]:
            with self.subTest(updates=updates):
                response = self.post(**updates)
                self.assertEqual(response.status_code, 400)
                self.assertIn(invalid_field, response.data)
                profile = GuestProfile.objects.get()
                self.assertEqual((profile.nickname, profile.supported_team), ('Original', 'g2'))

    def test_team_selection_is_private_and_does_not_create_game_or_user_data(self):
        response = self.post(supported_team='t1')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn(self.token, response.content.decode())
        self.assertNotIn(guest_identity_key(self.token), response.content.decode())
        self.assertEqual(Submission.objects.count(), 0)
        self.assertEqual(SubmissionAnswer.objects.count(), 0)
        self.assertEqual(SubmissionAttempt.objects.count(), 0)
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_team_selection_is_scoped_to_the_guest_identity(self):
        self.post(supported_team='t1')
        other = self.client.post(self.profile_url, {
            'guest_token': 'a593bade-bd60-4266-b001-bfe2723e81e9', 'supported_team': 'g2',
        }, format='json')
        self.assertEqual(other.status_code, 200)
        self.assertEqual(other.data['supported_team']['id'], 'g2')
        self.assertEqual(self.post().data['supported_team']['id'], 't1')

    def test_database_constraint_rejects_teams_outside_the_catalog(self):
        profile = GuestProfile.objects.create(guest_key=guest_identity_key(self.token), supported_team='t1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            GuestProfile.objects.filter(pk=profile.pk).update(supported_team='unknown')
        profile.refresh_from_db()
        self.assertEqual(profile.supported_team, 't1')

    def test_database_default_keeps_old_application_inserts_compatible(self):
        # An old backend instance does not yet include the new column in INSERT.
        table = connection.ops.quote_name(GuestProfile._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(f'''
                INSERT INTO {table} (guest_key, nickname, created_at, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING supported_team
            ''', [guest_identity_key(self.token), 'Existing'])
            self.assertEqual(cursor.fetchone()[0], '')
        self.assertEqual(GuestProfile.objects.get().nickname, 'Existing')


class GuestSupporterTeamMigrationTests(TransactionTestCase):
    def test_existing_guest_profile_survives_additive_migration(self):
        before = ('users', '0004_guestprofile')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([before])
        try:
            old_model = executor.loader.project_state([before]).apps.get_model('users', 'GuestProfile')
            old_profile = old_model.objects.create(guest_key='a' * 64, nickname='Historical')
            identity = old_profile.pk
            created = old_profile.created_at
            updated = old_profile.updated_at
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
        profile = GuestProfile.objects.get(pk=identity)
        self.assertEqual(profile.guest_key, 'a' * 64)
        self.assertEqual(profile.nickname, 'Historical')
        self.assertEqual(profile.supported_team, '')
        self.assertEqual(profile.created_at, created)
        self.assertEqual(profile.updated_at, updated)
