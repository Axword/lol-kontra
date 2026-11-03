from copy import deepcopy
import gzip
from hashlib import sha256
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from django.test import TestCase
from django.apps import apps
from django.db import connection

from apps.dailies.validators import PlayerFacts, evaluate_condition
from .career_roles import with_verified_career_roles
from .models import Player
from .test_worlds_import import snapshot
from .worlds_import import build_worlds_players
from .worlds_opponents import (SOURCE_SHA256, build_worlds_opponents, load_worlds_opponents,
                              with_worlds_opponents)


release = importlib.import_module('apps.players.migrations.0005_worlds_2026_october_19_release')
opponent_release = importlib.import_module('apps.players.migrations.0007_verified_worlds_opponents')


class WorldsOpponentSourceTests(unittest.TestCase):
    def test_exact_opposite_team_maps_and_wins_use_canonical_pages(self):
        data = snapshot(2)
        records, _ = build_worlds_players(data, [])
        document = build_worlds_opponents(data, records)
        relations = {row['slug']: row['relations'] for row in document['players']}
        first = relations['player-0']
        self.assertEqual(first['teams'], ['teamb'])
        self.assertEqual(first['players'], [f'player-{i}' for i in range(5, 10)])
        self.assertEqual(first['won_players'], first['players'])
        self.assertNotIn('player-1', first['players'])
        self.assertEqual(document['games'], 2)
        # A losing map counts as an opponent, never as a winning map.
        single = build_worlds_opponents(snapshot(), build_worlds_players(snapshot(), [])[0])
        loser = next(row for row in single['players'] if row['slug'] == 'player-5')
        self.assertEqual(loser['relations']['won_players'], [])
        self.assertEqual(loser['relations']['players'], [f'player-{i}' for i in range(5)])

    def test_2026_rows_never_enter_completed_edition_index(self):
        data = snapshot()
        page = '2026 Season World Championship/Main Event'
        data['tournaments'].append({'OverviewPage': page, 'Year': 2026})
        data['expected_game_counts'][page] = 1
        for row in deepcopy(data['rows']):
            row.update(game_id='2026-map', date='2026-10-01 12:00:00', tournament=page,
                       team='Gen.G' if row['team'] == 'Team A' else 'Team Z')
            data['rows'].append(row)
        records, _ = build_worlds_players(data, [])
        document = build_worlds_opponents(data, records)
        self.assertEqual(document['games'], 1)
        self.assertFalse(any('geng' in row['relations']['teams'] for row in document['players']))

    def test_invalid_source_rejects_incomplete_maps_and_unknown_results(self):
        for mutate in [lambda data: data['rows'].pop(),
                       lambda data: data['rows'][0].update(win='unknown'),
                       lambda data: data['rows'][0].update(player='not in aliases')]:
            data = snapshot()
            records, _ = build_worlds_players(data, [])
            mutate(data)
            with self.assertRaises(ValueError):
                build_worlds_opponents(data, records)

    def test_pinned_release_reproduces_all_relations_and_coverage(self):
        base = Path(__file__).resolve().parent / 'fixtures'
        source = gzip.decompress((base / 'worlds_source_snapshot.json.gz').read_bytes())
        self.assertEqual(sha256(source).hexdigest(), SOURCE_SHA256)
        document, records = opponent_release.load_release()
        rebuilt = build_worlds_opponents(json.loads(source), release.load_release(), SOURCE_SHA256)
        self.assertEqual(rebuilt, document)
        self.assertEqual((len(records), document['games']), (738, 1370))
        self.assertEqual(document['complete_through_year'], 2025)

    def test_real_predicates_have_broad_role_pools_and_keep_geng_separate(self):
        players = [SimpleNamespace(**with_worlds_opponents(with_verified_career_roles(row)))
                   for row in release.load_release()]
        expected = [('worlds_opponent_team', 'geng', 'mid', 26),
                    ('worlds_beat_player', 'faker', 'top', 23),
                    ('worlds_opponent_team', 'Dplus KIA', 'adc', 31)]
        for kind, value, role, count in expected:
            self.assertEqual(sum(role in PlayerFacts(player).roles and evaluate_condition(player, kind, 'eq', value)
                                 for player in players), count)
        # Samsung is not silently included in the Gen.G-only requirement.
        only_samsung = next(player for player in players
                            if evaluate_condition(player, 'worlds_opponent_team', 'eq', 'ssg')
                            and not evaluate_condition(player, 'worlds_opponent_team', 'eq', 'geng'))
        self.assertTrue(only_samsung)

    def test_every_new_type_is_positive_exact_and_requires_verified_metadata(self):
        faker = next(row for row in release.load_release() if row['slug'] == 'faker')
        player = SimpleNamespace(**with_worlds_opponents(faker))
        for kind, target in [('worlds_opponent_team', 'Gen.G'), ('worlds_opponent_player', 'ruler'),
                             ('worlds_beat_team', 'DWG KIA'), ('worlds_beat_player', 'ruler')]:
            self.assertTrue(evaluate_condition(player, kind, 'eq', target))
            for operator, value in [('gte', target), ('in', [target]), ('eq', False), ('eq', ''), ('any', target)]:
                self.assertFalse(evaluate_condition(player, kind, operator, value))
        for change in [{'complete': False}, {'scope': 'career'}, {'complete_through_year': 2026},
                       {'source_sha256': 'bad'}, {'teams': 'geng'}]:
            attrs = deepcopy(player.attributes)
            attrs['worlds_opponents'].update(change)
            changed = SimpleNamespace(**{**vars(player), 'attributes': attrs})
            self.assertFalse(evaluate_condition(changed, 'worlds_opponent_team', 'eq', 'geng'))
        self.assertFalse(evaluate_condition(SimpleNamespace(attributes={'teams': ['geng']}),
                                            'worlds_opponent_team', 'eq', 'geng'))
        self.assertFalse(evaluate_condition(player, 'worlds_opponent_player', 'eq', 'faker'))

    def test_overlay_preserves_other_fields_and_rejects_changed_identity(self):
        record = deepcopy(next(row for row in release.load_release() if row['slug'] == 'faker'))
        before = deepcopy(record)
        enriched = with_worlds_opponents(record)
        self.assertEqual(record, before)
        self.assertEqual(enriched['career_stats'], before['career_stats'])
        self.assertEqual(enriched['secondary_roles'], before['secondary_roles'])
        self.assertEqual({k:v for k,v in enriched['attributes'].items() if k != 'worlds_opponents'}, before['attributes'])
        record['attributes']['leaguepedia_page'] = 'Faker (different player)'
        self.assertIs(with_worlds_opponents(record), record)

    def test_question_catalog_offers_all_positive_families_as_broad_single_clues(self):
        from apps.dailies.generator import (CONDITION_POOL, WORLDS_OPPONENT_TYPES, build_condition_pool,
                                            single_candidate_limit)
        players = [SimpleNamespace(**with_worlds_opponents(with_verified_career_roles(row)))
                   for row in release.load_release()]
        conditions = [row for row in CONDITION_POOL if row[2] in WORLDS_OPPONENT_TYPES]
        self.assertEqual({row[2] for row in conditions}, WORLDS_OPPONENT_TYPES)
        self.assertEqual({row[0] for row in conditions}, {'worlds_opponent'})
        self.assertTrue(all('2026' in row[5] and '2026' in row[6] for row in conditions))
        catalog = build_condition_pool(players)
        for condition in conditions:
            self.assertIn(condition, catalog)
            self.assertEqual(single_candidate_limit(condition[2]), 60)
            role_counts = [sum(role in PlayerFacts(player).roles and evaluate_condition(player, *condition[2:5])
                               for player in players) for role in ['top', 'jungle', 'mid', 'adc', 'support']]
            self.assertTrue(any(18 <= count <= 60 for count in role_counts), (condition, role_counts))

    def test_tampered_evidence_fails_before_database_mutation(self):
        load_worlds_opponents.cache_clear()
        try:
            with patch.object(gzip, 'decompress', return_value=b'{}'):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    load_worlds_opponents()
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    opponent_release.load_release()
        finally:
            load_worlds_opponents.cache_clear()


class WorldsOpponentMigrationTests(TestCase):
    def test_additive_migration_is_idempotent_and_preserves_identity_statistics(self):
        record = deepcopy(next(row for row in release.load_release() if row['slug'] == 'faker'))
        record['attributes']['private_note'] = 'keep me'
        player = Player.objects.create(**record)
        pk, stats, roles = player.pk, deepcopy(player.career_stats), list(player.secondary_roles)
        opponent_release.install_opponents(apps, SimpleNamespace(connection=connection))
        player.refresh_from_db()
        self.assertEqual((player.pk, player.career_stats, player.secondary_roles), (pk, stats, roles))
        self.assertEqual(player.attributes['private_note'], 'keep me')
        first = deepcopy(player.attributes)
        opponent_release.install_opponents(apps, SimpleNamespace(connection=connection))
        player.refresh_from_db()
        self.assertEqual(player.attributes, first)
        self.assertTrue(evaluate_condition(player, 'worlds_opponent_team', 'eq', 'geng'))

    def test_canonical_conflict_rolls_back_every_player(self):
        records = [deepcopy(row) for row in release.load_release() if row['slug'] in {'faker', 'deft'}]
        for row in records:
            if row['slug'] == 'faker':
                row['attributes']['leaguepedia_page'] = 'Another person'
            Player.objects.create(**row)
        before = dict(Player.objects.values_list('slug', 'attributes'))
        with self.assertRaisesRegex(ValueError, 'canonical identity conflict'):
            opponent_release.install_opponents(apps, SimpleNamespace(connection=connection))
        self.assertEqual(dict(Player.objects.values_list('slug', 'attributes')), before)
