from copy import deepcopy
import gzip
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import Player, Team, TournamentAppearance


release = importlib.import_module('apps.players.migrations.0003_release_worlds_players')


class PlayerReleaseMigrationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.historical_apps = MigrationLoader(connection).project_state([
            ('players', '0002_alter_player_continent_alter_player_country_code_and_more')
        ]).apps
        cls.editor = SimpleNamespace(connection=connection)

    def test_release_seeds_complete_data_with_historical_models_without_network(self):
        with patch('apps.players.management.commands.seed_players.Command.handle', side_effect=AssertionError('runtime importer called')):
            release.install_release(self.historical_apps, self.editor)
        self.assertEqual(Player.objects.count(), 882)
        verified = list(Player.objects.filter(attributes__worlds_verified=True))
        self.assertEqual(len(verified), 738)
        self.assertEqual(sum(p.attributes.get('portrait_status') == 'available' for p in verified), 733)
        self.assertEqual(sum(p.career_stats['career']['complete'] for p in verified), 737)
        self.assertEqual(sum(p.attributes['worlds_eliminations_meta']['complete'] for p in verified), 697)
        self.assertTrue(all(p.career_stats['worlds']['complete'] and p.attributes['leagues_meta']['complete'] for p in verified))
        faker = Player.objects.get(slug='faker')
        self.assertIn(2013, faker.attributes['worlds_titles'])
        self.assertIsNotNone(faker.created_at)

    def test_replay_preserves_identity_progress_and_uncontrolled_metadata(self):
        player = Player.objects.create(slug='faker', nickname='Old Faker',
            attributes={'leaguepedia_page': 'FAKER', 'custom_note': {'keep': True}, 'worlds_titles': [1900]},
            career_stats={'msi': {'games': 123}, 'worlds': {'complete': False}})
        extra = Player.objects.create(slug='user-added-person', nickname='Local player')
        appearance = TournamentAppearance.objects.create(player=player, tournament_slug='preserved', year=2020,
                                                         team=Team.objects.create(slug='custom-team', name='Custom'))
        created, updated = player.created_at, player.updated_at
        release.install_release(self.historical_apps, self.editor)
        first = Player.objects.get(pk=player.pk)
        self.assertEqual(first.slug, 'faker')
        self.assertEqual(first.attributes['custom_note'], {'keep': True})
        self.assertEqual(first.career_stats['msi'], {'games': 123})
        self.assertEqual((first.created_at, first.updated_at), (created, updated))
        self.assertTrue(Player.objects.filter(pk=extra.pk).exists())
        self.assertEqual(TournamentAppearance.objects.get(pk=appearance.pk).player_id, player.pk)
        ids = dict(Player.objects.values_list('slug', 'pk'))
        with CaptureQueriesContext(connection) as queries:
            release.install_release(self.historical_apps, self.editor)
        self.assertFalse(any(query['sql'].lstrip().split()[0] in {'INSERT', 'UPDATE', 'DELETE'} for query in queries))
        self.assertEqual(dict(Player.objects.values_list('slug', 'pk')), ids)

    def test_wrong_hash_and_invalid_full_document_fail_before_any_database_query(self):
        source = release.load_release()
        broken = {'schema_version': 1, 'release': release.RELEASE_NAME, 'players': deepcopy(source)}
        broken['players'][-1]['worlds_count'] = -1
        with self.assertNumQueries(0):
            with self.assertRaisesRegex(ValueError, 'invalid Worlds counts'):
                release.validate_release(broken)
            with patch.object(Path, 'read_bytes', return_value=gzip.compress(b'{}', mtime=0)):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    release.install_release(self.historical_apps, self.editor)

    def test_duplicate_slug_and_lost_enrichment_cannot_silently_reduce_release(self):
        source = release.load_release()
        document = {'schema_version': 1, 'release': release.RELEASE_NAME, 'players': deepcopy(source)}
        document['players'][-1]['slug'] = document['players'][0]['slug']
        with self.assertRaisesRegex(ValueError, 'duplicate natural slug'):
            release.validate_release(document)
        document['players'] = deepcopy(source)
        next(row for row in document['players'] if row['attributes']['worlds_verified'])['career_stats'].pop('worlds')
        with self.assertRaisesRegex(ValueError, 'complete statistics'):
            release.validate_release(document)

    def test_canonical_identity_conflict_aborts_before_new_players_or_overwrite(self):
        player = Player.objects.create(slug='faker', nickname='Other person',
                                       attributes={'leaguepedia_page': 'A Different Person'})
        with self.assertRaisesRegex(ValueError, 'identity conflicts'):
            release.install_release(self.historical_apps, self.editor)
        self.assertEqual(Player.objects.count(), 1)
        player.refresh_from_db()
        self.assertEqual(player.nickname, 'Other person')

    def test_database_write_failure_rolls_back_earlier_insert_batch(self):
        model = self.historical_apps.get_model('players', 'Player')
        player = Player.objects.create(slug='faker', nickname='Old Faker')
        query_type = type(model.objects.all())
        with patch.object(query_type, 'update', side_effect=RuntimeError('Injected update failure')):
            with self.assertRaisesRegex(RuntimeError, 'Injected'):
                release.install_release(self.historical_apps, self.editor)
        self.assertEqual(Player.objects.count(), 1)
        player.refresh_from_db()
        self.assertEqual(player.nickname, 'Old Faker')
