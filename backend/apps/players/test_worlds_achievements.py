from copy import deepcopy
from datetime import datetime, timedelta
import unittest

from .worlds_achievements import _redirects, achievement_coverage, enrich_worlds_achievements


MAIN = '2018 Season World Championship/Main Event'
PLAYIN = '2018 Season World Championship/Play-In'


def snapshot():
    return {'scope': 'worlds_including_play_in', 'as_of': '2026-10-18T09:46:04+00:00',
            'tournaments': [{'OverviewPage': MAIN}, {'OverviewPage': PLAYIN}],
            'aliases': [], 'rows': [], 'achievements_source': {
                'source': 'Leaguepedia', 'complete': True, 'schedule': [], 'results': [],
                'season1_schedule_games': [],
            }}


def add_series(data, event, stage, number, teams, winners, rosters=None, best_of=3, date='2018-11-01T10:00:00'):
    key = f'{event}_{stage}_{number}'
    first = datetime.fromisoformat(date)
    for index, winner in enumerate(winners, 1):
        for side, team in enumerate(teams, 1):
            names = (rosters or {}).get(team, [f'{team}-{position}' for position in range(5)])
            for name in names:
                data['rows'].append({'game_id': f'{key}_{index}', 'tournament': event, 'team': team,
                                     'player': name, 'win': 'Yes' if winner == side else 'No',
                                     'date': (first + timedelta(hours=index - 1)).isoformat()})
    scores = [winners.count(1), winners.count(2)]
    decided = max(scores, default=0) >= best_of // 2 + 1
    match = {'tournament': event, 'match_id': key, 'team1': teams[0], 'team2': teams[1],
             'score1': scores[0], 'score2': scores[1], 'winner': 1 + int(scores[1] > scores[0]) if decided else None,
             'best_of': best_of, 'tab': stage, 'date': first.isoformat(), 'nullified': 0}
    data['achievements_source']['schedule'].append(match)
    return match


def records(*names):
    return [{'slug': name.casefold(), 'attributes': {'leaguepedia_page': name}} for name in names]


class WorldsAchievementTests(unittest.TestCase):
    def test_title_includes_playing_substitute_but_final_requires_actual_final_game(self):
        data = snapshot()
        add_series(data, MAIN, 'Day 1', 1, ('A', 'C'), [1], best_of=1,
                   rosters={'A': ['Duke', 'A-1', 'A-2', 'A-3', 'A-4']})
        add_series(data, MAIN, 'Quarterfinals', 1, ('A', 'E'), [1, 1])
        add_series(data, MAIN, 'Semifinals', 1, ('A', 'D'), [1, 1])
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1])
        enriched, report = enrich_worlds_achievements(data, records('Duke', 'A-0', 'B-0'))
        duke, final_winner, final_loser = [record['attributes'] for record in enriched]
        self.assertEqual(duke['worlds_titles'], [2018])
        self.assertEqual(duke['worlds_finals'], [])
        self.assertEqual(duke['worlds_semifinals'], [2018])
        self.assertEqual(duke['worlds_group_escapes'], [2018])
        self.assertEqual(enriched[0]['worlds_titles_count'], 1)
        self.assertEqual(final_winner['worlds_finals'], [2018])
        self.assertEqual(final_loser['worlds_finals'], [2018])
        self.assertEqual(final_loser['worlds_titles'], [])
        self.assertTrue(final_loser['worlds_titles_verified'])
        self.assertEqual(report['expected_game_counts'][MAIN], 7)

    def test_playin_final_cannot_award_world_champion_or_world_final(self):
        data = snapshot()
        add_series(data, PLAYIN, 'Finals', 1, ('A', 'B'), [1, 1])
        enriched, _ = enrich_worlds_achievements(data, records('A-0'))
        attributes = enriched[0]['attributes']
        self.assertNotIn('worlds_titles', attributes)
        self.assertNotIn('worlds_finals', attributes)
        self.assertEqual(attributes['worlds_playin_appearances'], [2018])
        self.assertNotIn('worlds_playin', attributes)

    def test_playin_advancement_requires_same_team_in_main_event(self):
        data = snapshot()
        add_series(data, PLAYIN, 'Round 2', 1, ('A', 'B'), [1, 1])
        add_series(data, MAIN, 'Day 1', 1, ('A', 'C'), [1], best_of=1)
        enriched, _ = enrich_worlds_achievements(data, records('A-0', 'B-0'))
        self.assertEqual(enriched[0]['attributes']['worlds_playin'], [2018])
        self.assertNotIn('worlds_playin', enriched[1]['attributes'])

    def test_unplayed_or_unfinished_future_finals_are_unknown(self):
        data = snapshot()
        event = '2026 Season World Championship/Main Event'
        data['tournaments'] = [{'OverviewPage': event}]
        add_series(data, event, 'Round 1', 1, ('A', 'C'), [1], best_of=1, date='2026-10-17T10:00:00')
        add_series(data, event, 'Finals', 1, ('A', 'B'), [], date='2026-11-01T10:00:00')
        enriched, report = enrich_worlds_achievements(data, records('A-0'))
        self.assertNotIn('worlds_titles', enriched[0]['attributes'])
        self.assertNotIn('worlds_finals', enriched[0]['attributes'])
        self.assertFalse(enriched[0]['attributes']['worlds_titles_verified'])
        self.assertNotIn(2026, report['known_years']['worlds_titles'])

    def test_incomplete_final_scoreboards_do_not_prove_champion(self):
        data = snapshot()
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1])
        data['rows'] = data['rows'][:10]
        enriched, report = enrich_worlds_achievements(data, records('A-0'))
        self.assertNotIn('worlds_titles', enriched[0]['attributes'])
        self.assertIn(MAIN, report['incomplete_events'])
        self.assertEqual(len(report['missing_series']), 1)

    def test_inconsistent_series_scores_do_not_prove_champion(self):
        data = snapshot()
        match = add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1])
        match.update(score1=0, score2=2, winner=2)
        enriched, report = enrich_worlds_achievements(data, records('B-0'))
        self.assertNotIn('worlds_titles', enriched[0]['attributes'])
        self.assertEqual(len(report['missing_series']), 1)

    def test_incomplete_ten_player_game_is_rejected(self):
        data = snapshot()
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1])
        data['rows'].pop()
        _, report = enrich_worlds_achievements(data, records('A-0'))
        self.assertEqual(len(report['invalid_games']), 1)
        self.assertEqual(report['schedule_coverage'][MAIN]['observed'], 1)

    def test_identity_redirects_use_source_pages_without_slug_guessing(self):
        data = snapshot()
        data['aliases'] = [{'alias': 'old name', 'page': 'Canonical Player'}]
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1],
                   rosters={'A': ['old name', 'A-1', 'A-2', 'A-3', 'A-4']})
        enriched, _ = enrich_worlds_achievements(data, records('Canonical Player', 'canonical-player'))
        self.assertEqual(enriched[0]['attributes']['worlds_titles'], [2018])
        self.assertNotIn('worlds_titles', enriched[1]['attributes'])

    def test_source_page_case_underscore_unicode_and_escaped_aliases_match(self):
        data = snapshot()
        data['players'] = [{'page': 'FabFabulous'}, {'page': 'Duke (Lee Ho-seong)'},
                           {'page': 'Å & B (Player)'}]
        data['aliases'] = [{'alias': 'old & name', 'page': 'Duke (Lee Ho-seong)'}]
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1],
                   rosters={'A': ['fabFabulous', 'OLD &amp; NAME', 'Ａ̊_&amp;_B_(Player)', 'A-3', 'A-4']})
        enriched, report = enrich_worlds_achievements(data, records('FabFabulous', 'duke_(Lee_Ho-seong)', 'Å & B (Player)'))
        for record in enriched:
            self.assertEqual(record['attributes']['worlds_titles'], [2018])
            self.assertEqual(record['attributes']['worlds_finals'], [2018])
        self.assertEqual(report['invalid_games'], [])

    def test_redirect_normalization_preserves_disambiguation(self):
        resolve = _redirects({'players': [{'page': 'Duke (Lee Ho-seong)'}, {'page': 'Duke (Other Player)'}]})
        self.assertEqual(resolve('DUKE_(Lee_Ho-seong)'), 'Duke (Lee Ho-seong)')
        self.assertNotEqual(resolve('Duke (Other Player)'), resolve('Duke (Lee Ho-seong)'))
        self.assertNotEqual(resolve('Duke'), resolve('Duke (Lee Ho-seong)'))

    def test_normalized_ambiguous_alias_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            _redirects({'aliases': [{'alias': 'old_name', 'page': 'First Player'},
                                    {'alias': 'OLD NAME', 'page': 'Second Player'}]})

    def test_normalized_alias_cannot_redirect_a_different_canonical_person(self):
        with self.assertRaisesRegex(ValueError, 'canonical player'):
            _redirects({'players': [{'page': 'First Player'}, {'page': 'Second Player'}],
                        'aliases': [{'alias': 'FIRST_PLAYER', 'page': 'Second Player'}]})

    def test_normalized_redirect_chain_and_cycle(self):
        resolve = _redirects({'aliases': [{'alias': 'Old Name', 'page': 'Middle Name'},
                                         {'alias': 'MIDDLE_NAME', 'page': 'Current Player'}]})
        self.assertEqual(resolve('OLD_NAME'), 'Current Player')
        cycle = _redirects({'aliases': [{'alias': 'Old Name', 'page': 'Middle Name'},
                                       {'alias': 'MIDDLE_NAME', 'page': 'OLD_NAME'}]})
        with self.assertRaisesRegex(ValueError, 'Cyclic'):
            cycle('old name')

    def test_case_variant_duplicate_player_invalidates_ten_player_game(self):
        data = snapshot()
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1],
                   rosters={'A': ['FABFABULOUS', 'fabFabulous', 'A-2', 'A-3', 'A-4']})
        enriched, report = enrich_worlds_achievements(data, records('FabFabulous'))
        self.assertEqual(len(report['invalid_games']), 2)
        self.assertNotIn('worlds_titles', enriched[0]['attributes'])

    def test_enrichment_and_coverage_do_not_mutate_inputs(self):
        data = snapshot()
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1])
        source_records = records('A-0')
        before, records_before = deepcopy(data), deepcopy(source_records)
        enrich_worlds_achievements(data, source_records)
        achievement_coverage(data)
        self.assertEqual(data, before)
        self.assertEqual(source_records, records_before)

    def test_direct_knockout_seed_is_not_claimed_as_group_escape(self):
        data = snapshot()
        add_series(data, MAIN, 'Quarterfinals', 1, ('A', 'C'), [1, 1])
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1])
        enriched, _ = enrich_worlds_achievements(data, records('A-0'))
        self.assertNotIn('worlds_group_escapes', enriched[0]['attributes'])

    def test_season1_forfeit_carry_over_is_not_a_physical_game(self):
        data = snapshot()
        event = 'Season 1 World Championship'
        data['tournaments'] = [{'OverviewPage': event}]
        match = add_series(data, event, 'Bracket Stage', 9, ('A', 'B'), [2, 1], date='2011-06-20T21:00:00')
        match.update(match_id=f'{event}_Finals_1', tab='Finals', score1=2, score2=1, winner=1)
        data['achievements_source']['season1_schedule_games'] = [
            {'game_id': f'{event}_Finals_1_{index}', 'match_id': match['match_id'],
             'blue': 'A', 'red': 'B', 'winner': winner, 'ff': 2 if index == 1 else None}
            for index, winner in enumerate([1, 2, 1], 1)
        ]
        enriched, report = enrich_worlds_achievements(data, records('A-0', 'B-0'))
        self.assertEqual(report['expected_game_counts'][event], 2)
        self.assertEqual(report['incomplete_events'], [])
        self.assertEqual(len(report['forfeit_points']), 1)
        self.assertEqual(enriched[0]['attributes']['worlds_titles'], [2011])
        self.assertEqual(enriched[1]['attributes']['worlds_finals'], [2011])

    def test_mismatched_as_of_rejects_stale_source(self):
        data = snapshot()
        data['achievements_source']['as_of'] = '2025-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError):
            enrich_worlds_achievements(data, records('A-0'))
