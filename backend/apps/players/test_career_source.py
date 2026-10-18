from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from .career_source import SourceError, build_career_overlay, fetch_career_snapshot


def records():
    return [{'slug': 'persistent-faker', 'id': 42, 'attributes': {'worlds_verified': True, 'leaguepedia_page': 'Faker'},
             'career_stats': {'worlds': {'games': 20}}}]


def source():
    groups = [{'page': 'Faker', 'champion': champion, 'games': games, 'wins': wins, 'losses': games - wins}
              for champion, games, wins in [('Ahri', 7, 4), ('Azir', 5, 3), ('Zed', 4, 2), ('Orianna', 3, 1),
                                           ('Ryze', 3, 1), ('Lux', 3, 1), ('Annie', 1, 1)]]
    return {'source': 'Leaguepedia', 'scope': 'leaguepedia_career', 'as_of': '2026-10-18T10:35:00+00:00',
            'aliases': [{'alias': 'Hide on Bush', 'page': 'Faker'}], 'rows': groups,
            'totals': [{'page': 'Faker', 'games': 26, 'wins': 13, 'losses': 13, 'invalid_game_rows': 0,
                        'invalid_result_rows': 0, 'future_rows': 0, 'undated_rows': 2}]}


class CareerSourceTests(TestCase):
    def test_complete_overlay_preserves_identity_and_every_champion_without_mutation(self):
        data, players = source(), records()
        before = deepcopy((data, players))
        overlay = build_career_overlay(data, players)
        player = overlay['players'][0]
        self.assertEqual(player['slug'], 'persistent-faker')
        self.assertEqual(player['leaguepedia_page'], 'Faker')
        stats = player['career_stats']['career']
        self.assertEqual((stats['games'], stats['wins'], stats['losses']), (26, 13, 13))
        self.assertEqual(len(stats['champions']), 7)
        self.assertTrue(stats['complete'])
        self.assertEqual(stats['scope'], 'leaguepedia_career')
        self.assertEqual(stats['coverage'], 'all_recorded_scoreboards')
        self.assertEqual(overlay['report']['undated_source_rows'], 2)
        self.assertEqual((data, players), before)

    def test_no_favorite_or_unverified_player_is_added(self):
        players = records() + [{'slug': 'unverified', 'attributes': {'worlds_verified': False, 'favorite_champions': ['Lux']}}]
        self.assertEqual(len(build_career_overlay(source(), players)['players']), 1)
        players[0]['attributes']['worlds_verified'] = False
        with self.assertRaises(SourceError):
            build_career_overlay(source(), players)

    def test_missing_independent_player_totals_or_entire_champion_group_rejects_import(self):
        for field in ('totals', 'rows'):
            data = source()
            data[field].pop()
            with self.subTest(field=field), self.assertRaises(SourceError):
                build_career_overlay(data, records())

    def test_duplicate_aggregate_is_deduplicated_but_conflict_is_rejected(self):
        data = source()
        data['rows'].append(deepcopy(data['rows'][0]))
        self.assertEqual(build_career_overlay(data, records())['report']['duplicate_aggregate_rows'], 1)
        data['rows'][-1].update(games=8, losses=4)
        with self.assertRaises(SourceError):
            build_career_overlay(data, records())

    def test_missing_unknown_and_conflicting_results_fail_closed(self):
        for field, value in [('wins', None), ('losses', 0), ('games', -1), ('games', True),
                             ('invalid_game_rows', 1), ('invalid_result_rows', 1), ('future_rows', 1)]:
            data = source()
            data['totals'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(SourceError):
                build_career_overlay(data, records())

    def test_null_champion_unknown_page_and_ambiguous_alias_fail_closed(self):
        for field, value in [('champion', None), ('champion', ''), ('champion', 'Ahri+Lux'), ('page', 'Another person')]:
            data = source()
            data['rows'][0][field] = value
            with self.subTest(field=field), self.assertRaises(SourceError):
                build_career_overlay(data, records())
        data = source()
        players = records() + [{'slug': 'other', 'attributes': {'worlds_verified': True, 'leaguepedia_page': 'Other'}}]
        data['aliases'].append({'alias': 'hide on bush', 'page': 'Other'})
        with self.assertRaisesRegex(SourceError, 'Ambiguous career alias'):
            build_career_overlay(data, players)

    def test_wrong_scope_source_and_naive_timestamp_are_rejected(self):
        for field, value in [('scope', 'worlds_including_play_in'), ('source', 'favorites'), ('as_of', '2026-01-01')]:
            data = source()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(SourceError):
                build_career_overlay(data, records())

    def test_fetch_uses_distinct_games_yes_no_and_independent_coverage(self):
        data = source()
        with patch('apps.players.career_source.CargoExport') as client_type:
            client = client_type.return_value
            client.query.side_effect = [data['totals'], data['aliases'], data['rows'], data['totals']]
            client.manifest = []
            snapshot = fetch_career_snapshot(records(), '/unused', progress=lambda _message: None, as_of=data['as_of'])
        self.assertEqual(snapshot['totals'], data['totals'])
        self.assertGreaterEqual(client_type.call_args.kwargs['interval'], 2)
        self.assertIn('COUNT(DISTINCT SP.GameId)', client.query.call_args_list[0].kwargs['fields'])
        self.assertIn('SP._ID IS NOT NULL', client.query.call_args_list[0].kwargs['where'])
        self.assertIn("SP.PlayerWin='Yes'", client.query.call_args_list[0].kwargs['fields'])
        self.assertTrue(client.query.call_args_list[-1].kwargs['refresh'])

    def test_source_changes_during_export_are_rejected(self):
        data = source()
        with patch('apps.players.career_source.CargoExport') as client_type:
            client_type.return_value.query.side_effect = [data['totals'], data['aliases'], data['rows'], []]
            with self.assertRaisesRegex(SourceError, 'changed while exporting'):
                fetch_career_snapshot(records(), '/unused', progress=lambda _message: None, as_of=data['as_of'])

    def test_explicit_partial_mode_never_marks_conflicting_game_totals_complete(self):
        data = source()
        data['totals'][0]['losses'] += 1
        with self.assertRaises(SourceError):
            build_career_overlay(data, records())
        overlay = build_career_overlay(data, records(), allow_incomplete=True)
        career = overlay['players'][0]['career_stats']['career']
        self.assertFalse(career['complete'])
        self.assertNotIn('games', career)
        self.assertNotIn('champions', career)
        self.assertEqual(overlay['report']['complete_players'], 0)
        self.assertEqual(overlay['report']['incomplete_players'][0]['page'], 'Faker')

    def test_command_validates_gzip_snapshot_without_writing_on_dry_run(self):
        from django.core.management import call_command
        with TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            root = Path(directory)
            (root / 'players.json').write_text(json.dumps(records()), encoding='utf-8')
            (root / 'source.json.gz').write_bytes(gzip.compress(json.dumps(source()).encode()))
            output = root / 'overlay.json'
            stream = io.StringIO()
            call_command('refresh_career_stats', input=str(root / 'players.json'), snapshot=str(root / 'source.json.gz'),
                         output=str(output), dry_run=True, stdout=stream)
            self.assertIn('1/1 players', stream.getvalue())
            self.assertFalse(output.exists())

    def test_command_progress_supports_export_retry_keyword_arguments(self):
        from django.core.management import call_command
        with TemporaryDirectory(dir=Path(__file__).resolve().parent) as directory:
            path = Path(directory) / 'players.json'
            path.write_text(json.dumps(records()), encoding='utf-8')

            def fetch(_records, _cache_dir, **kwargs):
                kwargs['progress']('Export retry 1/2', flush=True)
                return source()

            stream = io.StringIO()
            with patch('apps.players.management.commands.refresh_career_stats.fetch_career_snapshot', side_effect=fetch):
                call_command('refresh_career_stats', input=str(path), dry_run=True, stdout=stream)
            self.assertIn('Export retry', stream.getvalue())
