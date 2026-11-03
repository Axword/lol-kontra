from copy import deepcopy
from datetime import date
import gzip
import json
import random
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.players.career_roles import with_verified_career_roles
from apps.players.worlds_opponents import with_worlds_opponents
from .generator import requirement_key
from .board_factory import store_daily
from .match_boards import MIN_MATCH_CANDIDATES, audit_match_board, load_plan, match_for_day, store_match_board


def verified_players():
    root = Path(__file__).resolve().parents[1]
    release = json.loads(gzip.decompress((root / 'players/fixtures/releases/worlds_players_2026_10_19_v1.json.gz').read_bytes()))
    extra = json.loads((root / 'dailies/fixtures/releases/guest_board_2026_10_22_v1.json').read_text(encoding='utf-8'))
    overlays = {row['slug']: row['attributes'] for row in extra['players']}
    for row in release['players']:
        row['attributes'].update(overlays.get(row['slug'], {}))
    return [SimpleNamespace(pk=i + 1, **with_worlds_opponents(with_verified_career_roles(row)))
            for i, row in enumerate(release['players'])]


class PlannedMatchBoardTests(SimpleTestCase):
    def test_three_confirmed_match_drafts_are_broad_diverse_and_playable(self):
        players = verified_players()
        previous = set()
        expected = {'2026-11-04': [31, 21, 26, 26, 29], '2026-11-05': [23, 20, 30, 18, 58], '2026-11-06': [22, 21, 18, 26, 24]}
        for day, counts in expected.items():
            board = match_for_day(day)
            self.assertEqual(board['review_status'], 'approved' if day == '2026-11-04' else 'draft')
            pools = audit_match_board(board, players)
            self.assertEqual([len(pool) for pool in pools], counts)
            self.assertTrue(all(len(pool) >= MIN_MATCH_CANDIDATES for pool in pools))
            self.assertEqual(sorted(len(slot['conditions']) for slot in board['slots']), [1, 1, 2, 2, 2])
            facts = set()
            for slot, pool in zip(board['slots'], pools):
                self.assertEqual(sorted(p.slug for p in pool), slot['audited_candidates'])
                for c in slot['conditions']:
                    key = requirement_key(c['condition_type'], c['operator'], c['value'])
                    self.assertNotIn(key, facts)
                    facts.add(key)
            # Familiar facts may recur on another day, but the next board must
            # offer a substantially different set of choices and combinations.
            self.assertLessEqual(len(facts & previous), 2)
            previous = facts

    def test_today_is_excluded_and_unknown_opponents_remain_pending(self):
        self.assertIsNone(match_for_day(date(2026, 11, 3)))
        self.assertEqual(load_plan()['timezone'], 'Europe/Warsaw')
        for day in ('2026-11-07', '2026-11-08', '2026-11-14'):
            board = match_for_day(day)
            self.assertEqual(board['teams'], [])
            self.assertEqual(board['review_status'], 'pending_matchup')
            with self.assertRaisesRegex(ValueError, 'actual opponents'):
                audit_match_board(board, [])

    def test_unapproved_match_leaves_generic_generation_available_without_database_access(self):
        for day in (date(2026, 11, 5), date(2026, 11, 7)):
            self.assertIsNone(store_match_board(SimpleNamespace(date=day)))
        self.assertIsNone(store_match_board(SimpleNamespace(date=date(2026, 11, 3))))

    def test_draft_and_pending_calendar_entries_do_not_interrupt_the_generic_writer(self):
        for day in (date(2026, 11, 5), date(2026, 11, 7)):
            with self.subTest(day=day), patch('apps.dailies.board_factory.question_catalog',
                    side_effect=RuntimeError('generic catalog reached')) as catalog:
                with self.assertRaisesRegex(RuntimeError, 'generic catalog reached'):
                    store_daily(SimpleNamespace(date=day), random.Random(1), {})
                catalog.assert_called_once_with()

    def test_an_existing_board_cannot_be_rewritten_even_after_approval(self):
        approved = deepcopy(match_for_day('2026-11-04'))
        approved['review_status'] = 'approved'
        old = SimpleNamespace(date=date(2026, 11, 4), slots=SimpleNamespace(exists=lambda: True))
        with patch('apps.dailies.match_boards.match_for_day', return_value=approved):
            with self.assertRaisesRegex(ValueError, 'retain their slots'):
                store_match_board(old)

    def test_repeated_origin_and_unrelated_match_context_are_rejected(self):
        board = deepcopy(match_for_day('2026-11-04'))
        origin = {'condition_type': 'birth_country', 'operator': 'eq', 'value': 'CN',
                  'label_pl': 'Urodzony w Chinach', 'label_en': 'Born in China'}
        board['slots'][1]['conditions'].append(origin)
        with self.assertRaises(ValueError):
            audit_match_board(board, [])
        board = deepcopy(match_for_day('2026-11-04'))
        for slot in board['slots']:
            slot['match_context'] = ''
        with self.assertRaisesRegex(ValueError, 'scheduled match'):
            audit_match_board(board, [])

    def test_authored_board_cannot_bypass_the_minimum_number_of_valid_answers(self):
        board = deepcopy(match_for_day('2026-11-04'))
        board['slots'][0]['conditions'] = [{
            'condition_type': 'worlds_team_year', 'operator': 'eq',
            'value': {'team': 'gen-g', 'before': 2024},
            'label_pl': 'Grał na Worlds w Gen.G przed 2024 rokiem',
            'label_en': 'Played for Gen.G at Worlds before 2024',
        }]
        with self.assertRaisesRegex(ValueError, '18–150'):
            audit_match_board(board, verified_players())
