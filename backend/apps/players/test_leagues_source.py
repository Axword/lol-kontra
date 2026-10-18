from copy import deepcopy
import gzip
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from apps.dailies.validators import evaluate_condition
from .leagues_source import SCOPE, SourceError, build_leagues_overlay, fetch_leagues_snapshot


AS_OF = '2026-10-18T09:46:04Z'


def records():
    return [{'id': 42, 'slug': 'persistent-kuro', 'residency': 'LEC', 'attributes': {
        'worlds_verified': True, 'leaguepedia_page': 'Kuro', 'leagues': ['LEC'], 'portrait_url': 'preserve'},
        'career_stats': {'worlds': {'games': 123}}}]


def source():
    return {'source': 'Leaguepedia', 'scope': SCOPE, 'as_of': AS_OF,
        'league_catalogue': [{'league': name, 'level': 'Primary', 'official': 'Yes'} for name in
                             ['LoL The Champions', 'Tencent LoL Pro League']],
        'totals': [{'page': 'Kuro', 'games': 12, 'invalid_game_rows': 0, 'invalid_event_rows': 0}],
        'rows': [{'page': 'Kuro', 'league': name, 'games': games,
                  'example_event': event, 'first_game': '2014-01-01T00:00:00Z', 'last_game': '2020-01-01T00:00:00Z'}
                 for name, games, event in [('LoL The Champions', 10, 'Champions/2014 Season/Summer Season'),
                                             ('Tencent LoL Pro League', 2, 'LPL/2019 Season/Spring Season')]],
        'manifest': [{'params': {'tables': 'source'}, 'rows': 2, 'sha256': 'source-hash'}]}


class LeagueSourceTests(TestCase):
    def test_kuro_overlay_replaces_false_lec_with_actual_lck_lpl_without_mutating_inputs(self):
        data, players = source(), records()
        original = deepcopy((data, players))
        overlay = build_leagues_overlay(data, players)
        row = overlay['players'][0]
        self.assertEqual(row['slug'], 'persistent-kuro')
        self.assertEqual(row['leaguepedia_page'], 'Kuro')
        self.assertEqual(row['attributes']['leagues'], ['LCK', 'LPL'])
        self.assertTrue(row['attributes']['leagues_meta']['complete'])
        self.assertEqual(row['attributes']['leagues_meta']['games'], 12)
        self.assertEqual(overlay['report']['changed_players'], 1)
        self.assertEqual((data, players), original)

    def test_historical_families_are_explicit_and_international_names_do_not_imply_regions(self):
        data = source()
        labels = ['Europe League Championship Series', 'North America League Championship Series',
                  'Pacific Championship Series', 'Rift Rivals 2017 NA-EU']
        data['league_catalogue'] = [{'league': label, 'official': 'Yes', 'level': 'Primary'} for label in labels]
        data['rows'] = [{**data['rows'][0], 'league': label, 'games': 3} for label in labels]
        overlay = build_leagues_overlay(data, records())
        self.assertEqual(overlay['players'][0]['attributes']['leagues'], ['LCS', 'LEC', 'PCS'])
        self.assertEqual(overlay['report']['unmapped_source_labels'], {'Rift Rivals 2017 NA-EU': 3})

    def test_missing_league_is_audited_without_country_or_residency_guessing(self):
        data = source()
        data['rows'] = [{**data['rows'][0], 'league': None, 'games': 12}]
        row = build_leagues_overlay(data, records())['players'][0]
        self.assertEqual(row['attributes']['leagues'], [])
        self.assertEqual(row['attributes']['leagues_meta']['league_groups'][0]['league'], None)

    def test_sea_tour_uses_official_redirect_proof_and_never_infers_lcs_or_lec(self):
        data = source()
        data['rows'] = [{**data['rows'][0], 'league': 'SEA Tour', 'games': 12}]
        data['league_catalogue'] = [{'league': 'League of Legends SEA Tour', 'level': 'Primary', 'official': 'Yes'}]
        with self.assertRaisesRegex(SourceError, 'redirect evidence'):
            build_leagues_overlay(data, records())
        data['league_aliases'] = {'source_url': 'https://lol.fandom.com/api.php',
            'response': {'query': {'redirects': [{'from': 'SEA Tour', 'to': 'League of Legends SEA Tour'}]}}}
        self.assertEqual(build_leagues_overlay(data, records())['players'][0]['attributes']['leagues'], ['LST'])
        data['league_aliases']['response']['query']['redirects'][0]['to'] = 'LoL EMEA Championship'
        with self.assertRaisesRegex(SourceError, 'redirect evidence'):
            build_leagues_overlay(data, records())

    def test_missing_groups_totals_and_duplicate_groups_reject_incomplete_coverage(self):
        for change in ['drop_group', 'drop_total', 'duplicate']:
            data = source()
            if change == 'drop_group':
                data['rows'].pop()
            elif change == 'drop_total':
                data['totals'].clear()
            else:
                data['rows'].append(deepcopy(data['rows'][0]))
            with self.subTest(change=change), self.assertRaises(SourceError):
                build_leagues_overlay(data, records())

    def test_invalid_identity_counts_cutoff_and_unofficial_mapped_labels_fail_closed(self):
        for field, value in [('games', True), ('games', -1), ('page', 'Different Kuro'),
                             ('example_event', None), ('last_game', AS_OF), ('first_game', '2020-01-01')]:
            data = source()
            data['rows'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(SourceError):
                build_leagues_overlay(data, records())
        data = source()
        data['league_catalogue'][0]['official'] = 'No'
        with self.assertRaises(SourceError):
            build_leagues_overlay(data, records())

    def test_fetch_checks_actual_game_identity_cutoff_group_count_and_unchanged_totals(self):
        data = source()
        with patch('apps.players.leagues_source.CargoExport') as factory:
            client = factory.return_value
            client.all.return_value = data['league_catalogue']
            client.query.side_effect = [data['totals'], [{'page': 'Kuro', 'groups': 2}], data['rows'], data['totals']]
            client.manifest = data['manifest']
            result = fetch_leagues_snapshot(records(), '/unused', as_of=AS_OF, progress=lambda _message: None)
        self.assertEqual(result['manifest'], data['manifest'])
        self.assertGreaterEqual(factory.call_args.kwargs['interval'], 2)
        query = client.query.call_args_list[0].kwargs
        self.assertIn('SP._ID IS NOT NULL', query['where'])
        self.assertIn("SP.DateTime_UTC<'2026-10-18 09:46:04'", query['where'])
        self.assertIn('COUNT(DISTINCT SP.GameId)', query['fields'])
        grouped = client.query.call_args_list[2].kwargs
        self.assertIn('SP.OverviewPage=T.OverviewPage', grouped['join_on'])
        self.assertIn('T.League=league', grouped['fields'])
        self.assertTrue(client.query.call_args_list[-1].kwargs['refresh'])

    def test_truncated_pagination_or_changing_source_never_returns_an_overlay(self):
        data = source()
        for responses in [[data['totals'], [{'page': 'Kuro', 'groups': 2}], []],
                          [data['totals'], [{'page': 'Kuro', 'groups': 2}], data['rows'], []]]:
            with self.subTest(responses=len(responses)), patch('apps.players.leagues_source.CargoExport') as factory:
                factory.return_value.all.return_value = data['league_catalogue']
                factory.return_value.query.side_effect = responses
                with self.assertRaises(SourceError):
                    fetch_leagues_snapshot(records(), '/unused', as_of=AS_OF, progress=lambda _message: None)

    def test_command_offline_gzip_writes_only_separate_overlay_and_source(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = json.dumps(records()).encode()
            input_path, source_path = root / 'players.json', root / 'source.json.gz'
            input_path.write_bytes(original)
            source_path.write_bytes(gzip.compress(json.dumps(source()).encode()))
            output, saved = root / 'overlay.json', root / 'copy.json.gz'
            call_command('refresh_leagues', input=str(input_path), snapshot=str(source_path),
                         output=str(output), save_snapshot=str(saved), stdout=StringIO())
            self.assertEqual(input_path.read_bytes(), original)
            self.assertEqual(json.loads(output.read_text())['players'][0]['attributes']['leagues'], ['LCK', 'LPL'])
            self.assertEqual(json.loads(gzip.decompress(saved.read_bytes())), source())
            with self.assertRaisesRegex(CommandError, 'separate'):
                call_command('refresh_leagues', input=str(input_path), snapshot=str(source_path),
                             output=str(input_path), stdout=StringIO())
            self.assertEqual(input_path.read_bytes(), original)

    def test_source_backed_empty_or_incomplete_leagues_never_restore_stale_residency(self):
        meta = {'source': 'Leaguepedia', 'scope': SCOPE, 'complete': True}
        player = SimpleNamespace(residency='LEC', country_code='KR', continent='Asia',
                                 attributes={'leagues': [], 'leagues_meta': meta})
        for kind in ['residency', 'region', 'league']:
            self.assertFalse(evaluate_condition(player, kind, 'eq', 'LEC'))
        player.attributes['leagues'] = ['LCK', 'LPL']
        self.assertTrue(evaluate_condition(player, 'league', 'eq', 'LCK'))
        self.assertFalse(evaluate_condition(player, 'league', 'eq', 'LEC'))
        meta['complete'] = False
        self.assertFalse(evaluate_condition(player, 'league', 'eq', 'LCK'))
        player.attributes = {}
        self.assertTrue(evaluate_condition(player, 'league', 'eq', 'LEC'))
