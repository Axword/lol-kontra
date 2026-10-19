from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import unittest

from apps.dailies.validators import _champion_name
from .worlds_import import _key
from .worlds_refresh import WORLD_ATTRIBUTES, refresh_worlds_records


FIXTURES = Path(__file__).resolve().parent / 'fixtures'
AFFECTED = {'busio', 'caliste', 'canna', 'chika', 'gury', 'harky',
            'kratos-ngo-duc-khanh', 'kyeahoo', 'siuloong', 'yike'}
WINNERS = {'busio', 'caliste', 'canna', 'kyeahoo', 'yike'}


def load(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


class WorldsCurrentRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = load(FIXTURES / 'worlds_source_snapshot.json.gz')
        cls.career = load(FIXTURES / 'leaguepedia_career_refresh_2026_10_19.json.gz')
        cls.records = load(FIXTURES / 'worlds_players_full.json')
        cls.old = {record['slug']: record for record in load(FIXTURES / 'releases/worlds_players_2026_10_18_v1.json.gz')['players']}
        cls.current = {record['slug']: record for record in cls.records}

    def test_current_source_has_twenty_two_playin_maps_and_no_future_scoreboards(self):
        rows = [row for row in self.snapshot['rows'] if row['tournament'].startswith('2026 ')]
        self.assertEqual(len(rows), 220)
        self.assertEqual(len({row['game_id'] for row in rows}), 22)
        self.assertEqual({row['tournament'] for row in rows}, {'2026 Season World Championship/Play-In'})
        cutoff = datetime.fromisoformat(self.snapshot['as_of'].replace('Z', '+00:00'))
        for row in self.snapshot['rows']:
            played = datetime.fromisoformat(row['date'].replace('Z', '+00:00'))
            if played.tzinfo is None:
                played = played.replace(tzinfo=timezone.utc)
            self.assertLessEqual(played, cutoff)

    def test_exactly_ten_careers_gain_the_three_independently_verified_games(self):
        changed = {slug for slug, record in self.current.items()
                   if record['career_stats'].get('career') != self.old[slug]['career_stats'].get('career')}
        self.assertEqual(changed, AFFECTED)
        for slug in AFFECTED:
            for scope in ('worlds', 'career'):
                before, after = self.old[slug]['career_stats'][scope], self.current[slug]['career_stats'][scope]
                self.assertEqual(after['games'] - before['games'], 3, (slug, scope))
                self.assertEqual(after['wins'] - before['wins'], 3 if slug in WINNERS else 0)
                self.assertEqual(after['losses'] - before['losses'], 0 if slug in WINNERS else 3)
                self.assertEqual(sum(row['games'] for row in after['champions']), after['games'])
                self.assertEqual(sum(row['wins'] for row in after['champions']), after['wins'])
                self.assertTrue(after['complete'])

    def test_new_career_champion_counts_match_the_actual_three_maps(self):
        additions = [row for row in self.snapshot['rows'] if row['game_id'].startswith(
            '2026 Season World Championship/Play-In_Round 3_1_')]
        self.assertEqual(len(additions), 30)
        for slug in AFFECTED:
            record = self.current[slug]
            page = _key(record['attributes']['leaguepedia_page'])
            expected_games, expected_wins = Counter(), Counter()
            for row in additions:
                if _key(row['player']) == page:
                    champion = _champion_name(row['champion'])
                    expected_games[champion] += 1
                    expected_wins[champion] += row['win'] == 'Yes'
            for scope in ('worlds', 'career'):
                prior = {_champion_name(row['champion']): row for row in self.old[slug]['career_stats'][scope]['champions']}
                after = {_champion_name(row['champion']): row for row in record['career_stats'][scope]['champions']}
                for champion in set(prior) | set(after):
                    self.assertEqual(after.get(champion, {}).get('games', 0) - prior.get(champion, {}).get('games', 0),
                                     expected_games[champion], (slug, scope, champion))
                    self.assertEqual(after.get(champion, {}).get('wins', 0) - prior.get(champion, {}).get('wins', 0),
                                     expected_wins[champion], (slug, scope, champion))

    def test_player_identities_portraits_leagues_and_unrelated_metadata_are_preserved(self):
        self.assertEqual(len(self.current), 882)
        self.assertEqual(self.current.keys(), self.old.keys())
        for slug, record in self.current.items():
            old = self.old[slug]
            for key in ('nickname', 'real_name', 'birth_year', 'country_code', 'residency', 'continent',
                        'primary_role', 'secondary_roles', 'is_active'):
                self.assertEqual(record[key], old[key], (slug, key))
            self.assertEqual({key: value for key, value in record['attributes'].items() if key not in WORLD_ATTRIBUTES},
                             {key: value for key, value in old['attributes'].items() if key not in WORLD_ATTRIBUTES}, slug)
            for key in ('worlds_appearances', 'worlds_titles', 'worlds_finals', 'worlds_semifinals', 'worlds_group_escapes'):
                self.assertTrue(set(old['attributes'].get(key, [])) <= set(record['attributes'].get(key, [])), (slug, key))

    def test_kc_advancement_and_all_three_playin_eliminations_are_known(self):
        for record in self.records:
            years = record['attributes'].get('worlds_team_years', {})
            if 2026 in years.get('Karmine Corp', []):
                self.assertIn(2026, record['attributes']['worlds_playin'])
                self.assertNotIn(2026, record['attributes'].get('worlds_titles', []))
            if any(2026 in years.get(team, []) for team in ('MVK Esports', 'Cloud9', 'FURIA')):
                self.assertIn(2026, record['attributes']['worlds_eliminations']['play_in'])

    def test_pinned_refresh_is_idempotent_and_does_not_mutate_its_inputs(self):
        before = deepcopy(self.records)
        updated, report = refresh_worlds_records(self.snapshot, self.records, self.career)
        self.assertEqual(updated, self.records)
        self.assertEqual(self.records, before)
        self.assertEqual(report['changed_records'], 0)
        self.assertEqual(set(report['career_refreshed_slugs']), AFFECTED)
        self.assertEqual(report['new_players'], 0)
        self.assertEqual(report['achievements']['invalid_games'], [])
        self.assertEqual(report['achievements']['incomplete_events'], [])
        self.assertEqual(report['achievements']['missing_series'], [])
