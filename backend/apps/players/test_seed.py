import io
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase

from .models import Player
from .serializers import PlayerAutocompleteSerializer, PlayerListSerializer


class PlayerImportRegressionTests(TestCase):
    def import_rows(self, rows):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'players.json'
            path.write_text(json.dumps(rows), encoding='utf-8')
            call_command('seed_players', file=str(path), stdout=io.StringIO())

    def test_duplicate_placeholder_does_not_overwrite_verified_identity(self):
        self.import_rows([
            {'slug': 'caps', 'nickname': 'Caps', 'real_name': 'Rasmus Winther',
             'country_code': 'DK', 'residency': 'LEC', 'continent': 'Europe',
             'primary_role': 'mid', 'birth_year': 1999, 'worlds_count': 2,
             'attributes': {'worlds_appearances': [2018, 2019], 'teams': ['Fnatic', 'G2']}},
            {'slug': 'caps', 'nickname': 'caPs', 'country_code': 'KR', 'residency': 'LCK',
             'attributes': {'worlds_appearances': [2022], 'teams': ['G2']}},
        ])
        player = Player.objects.get(slug='caps')
        self.assertEqual(player.nickname, 'Caps')
        self.assertEqual(player.country_code, 'DK')
        self.assertEqual(player.residency, 'LEC')
        self.assertEqual(player.attributes['worlds_appearances'], [2018, 2019])

    def test_reimport_updates_existing_large_database(self):
        Player.objects.bulk_create([
            Player(slug=f'player-{i}', nickname=f'Player {i}') for i in range(701)
        ])
        self.import_rows([{'slug': 'player-0', 'nickname': 'Updated', 'primary_role': 'top'}])
        self.assertEqual(Player.objects.get(slug='player-0').nickname, 'Updated')

    def test_html_names_and_string_booleans_are_normalized(self):
        self.import_rows([{
            'slug': 'test', 'nickname': 'Test', 'real_name': 'Carl&amp;nbsp;Martin Larsson',
            'is_active': 'false', 'country_code': None, 'primary_role': 'mid',
        }])
        player = Player.objects.get(slug='test')
        self.assertEqual(player.real_name, 'Carl Martin Larsson')
        self.assertFalse(player.is_active)
        self.assertEqual(player.country_code, '')

    def test_imported_unverified_empty_titles_cannot_prove_never_won(self):
        self.import_rows([{
            'slug': 'faker', 'nickname': 'Faker', 'worlds_count': 9,
            'attributes': {'worlds_titles': [], 'worlds_appearances': list(range(2015, 2024))},
        }])
        self.assertNotIn('worlds_titles', Player.objects.get(slug='faker').attributes)

    def test_canonical_source_restores_early_worlds_and_historical_roles(self):
        call_command('seed_players', sample=True, stdout=io.StringIO())
        self.assertIn(2013, Player.objects.get(slug='faker').attributes['worlds_appearances'])
        self.assertIn('adc', Player.objects.get(slug='perkz').secondary_roles)
        self.assertIn('adc', Player.objects.get(slug='rekkles').secondary_roles)
        caps = Player.objects.get(slug='caps')
        self.assertEqual((caps.nickname, caps.country_code, caps.residency), ('Caps', 'DK', 'LEC'))
        self.assertIn(2022, caps.attributes['worlds_appearances'])

    def test_canonical_unenriched_records_have_no_invented_country_or_league(self):
        data = json.loads((Path(__file__).parent / 'fixtures' / 'worlds_players_full.json').read_text(encoding='utf-8'))
        unknown = [item for item in data if not item.get('real_name') and not item.get('birth_year')]
        self.assertTrue(unknown)
        for item in unknown:
            with self.subTest(slug=item['slug']):
                self.assertEqual(item['country_code'], '')
                self.assertEqual(item['residency'], '')
                self.assertEqual(item['attributes']['leagues'], [])
                self.assertFalse(item['attributes']['activity_verified'])

    def test_public_serializers_do_not_claim_unknown_activity_or_zero_titles(self):
        player = Player(slug='unknown', nickname='Unknown', attributes={'activity_verified': False})
        for serializer in (PlayerListSerializer, PlayerAutocompleteSerializer):
            data = serializer(player).data
            self.assertNotIn('is_active', data)
            self.assertNotIn('worlds_titles_count', data)
            self.assertNotIn('attributes', data)

    def test_refresh_keeps_identity_and_unrelated_stats_but_removes_false_rankings(self):
        old = Player.objects.create(slug='caps', nickname='Caps',
            attributes={'top_champions_career': ['Ahri'], 'pentakills_worlds': 9},
            career_stats={'msi': {'games': 4}, 'worlds': {'games': 999}})
        self.import_rows([{'slug': 'caps', 'nickname': 'Caps',
            'attributes': {'favorite_champions': ['Ahri'], 'pentakills_worlds_verified': False},
            'career_stats': {'worlds': {'games': 20}}}])
        updated = Player.objects.get(slug='caps')
        self.assertEqual(updated.pk, old.pk)
        self.assertEqual(updated.career_stats, {'msi': {'games': 4}, 'worlds': {'games': 20}})
        self.assertNotIn('top_champions_career', updated.attributes)
        self.assertNotIn('pentakills_worlds', updated.attributes)

    def test_ineligible_worlds_record_cannot_keep_stale_complete_stats(self):
        Player.objects.create(slug='iem', nickname='IEM', career_stats={'worlds': {'complete': True}})
        self.import_rows([{'slug': 'iem', 'attributes': {'worlds_verified': False}}])
        self.assertNotIn('worlds', Player.objects.get(slug='iem').career_stats)

    def test_search_exposes_only_verified_leaguepedia_portrait_urls(self):
        official = 'https://static.wikia.nocookie.net/lolesports_gamepedia/images/example.png'
        player = Player(slug='portrait', nickname='Portrait',
                        attributes={'portrait_url': official, 'portrait_source': 'Leaguepedia'})
        self.assertEqual(PlayerAutocompleteSerializer(player).data['portrait_url'], official)
        for url in ['http://static.wikia.nocookie.net/image.png', 'https://example.com/image.png',
                    'https://static.wikia.nocookie.net@example.com/image.png', 'javascript:bad']:
            player.attributes['portrait_url'] = url
            self.assertIsNone(PlayerAutocompleteSerializer(player).data['portrait_url'])
        player.attributes = {'portrait_url': official, 'portrait_source': 'Other'}
        self.assertIsNone(PlayerAutocompleteSerializer(player).data['portrait_url'])
