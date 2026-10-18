from copy import deepcopy
import unittest

from .test_worlds_achievements import MAIN, PLAYIN, add_series, records, snapshot
from .worlds_eliminations import STAGES, enrich_worlds_eliminations


def with_final(data):
    add_series(data, MAIN, 'Finals', 1, ('A', 'E'), [1, 1])
    return data


def placed(data, team, year=2018, qualified=0):
    data.setdefault('eliminations_source', {'source': 'Leaguepedia', 'complete': True,
                                          'as_of': data['as_of'], 'results': []})['results'].append({
        'tournament': f'{year} Season World Championship', 'team': team,
        'place_number': 17, 'qualified': qualified, 'date': f'{year}-11-01',
    })


class WorldsEliminationTests(unittest.TestCase):
    def test_main_knockout_loser_stage_and_swiss_loss_are_distinct(self):
        data = snapshot()
        for index, teams in enumerate((('A', 'B'), ('C', 'D'), ('E', 'F'), ('G', 'H')), 1):
            add_series(data, MAIN, 'Quarterfinals', index, teams, [1, 1])
        add_series(data, MAIN, 'Semifinals', 1, ('A', 'C'), [1, 1])
        add_series(data, MAIN, 'Semifinals', 2, ('E', 'G'), [1, 1])
        add_series(data, MAIN, 'Round 1', 1, ('A', 'I'), [1], best_of=1)
        with_final(data)
        enriched, report = enrich_worlds_eliminations(data, records('A-0', 'B-0', 'C-0', 'E-0', 'I-0'))
        expected = (None, 'quarterfinal', 'semifinal', 'final', 'group')
        for record, eliminated_stage in zip(enriched, expected):
            self.assertEqual(record['attributes']['worlds_eliminations'],
                             {stage: [2018] if stage == eliminated_stage else [] for stage in STAGES})
            self.assertTrue(record['attributes']['worlds_eliminations_meta']['complete'])
        self.assertEqual(report['unknown_teams'], [])

    def test_elimination_applies_to_substitute_who_played_earlier_in_event(self):
        data = snapshot()
        add_series(data, MAIN, 'Day 1', 1, ('E', 'B'), [1], best_of=1,
                   rosters={'E': ['Substitute', 'E-1', 'E-2', 'E-3', 'E-4']})
        with_final(data)
        enriched, _ = enrich_worlds_eliminations(data, records('Substitute', 'E-0'))
        for record in enriched:
            self.assertEqual(record['attributes']['worlds_eliminations']['final'], [2018])

    def test_playin_early_loss_does_not_eliminate_an_advancing_team(self):
        data = snapshot()
        add_series(data, PLAYIN, 'Round 1', 1, ('A', 'K'), [2, 2])
        add_series(data, PLAYIN, 'Round 2', 1, ('A', 'J'), [1, 1])
        placed(data, 'J')
        placed(data, 'K')
        with_final(data)
        enriched, _ = enrich_worlds_eliminations(data, records('A-0', 'J-0', 'K-0'))
        self.assertEqual(enriched[0]['attributes']['worlds_eliminations']['play_in'], [])
        self.assertEqual(enriched[1]['attributes']['worlds_eliminations']['play_in'], [2018])
        self.assertEqual(enriched[2]['attributes']['worlds_eliminations']['play_in'], [2018])

    def test_absence_from_main_without_official_eliminated_placement_stays_unknown(self):
        data = snapshot()
        add_series(data, PLAYIN, 'Round 2', 1, ('A', 'J'), [1, 1])
        placed(data, 'J', qualified=1)
        with_final(data)
        enriched, report = enrich_worlds_eliminations(data, records('J-0'))
        self.assertNotIn('worlds_eliminations', enriched[0]['attributes'])
        self.assertFalse(enriched[0]['attributes']['worlds_eliminations_meta']['complete'])
        self.assertTrue(report['unknown_teams'])

    def test_direct_knockout_seed_is_never_labelled_group_eliminated(self):
        data = snapshot()
        add_series(data, MAIN, 'Quarterfinals', 1, ('A', 'B'), [1, 1])
        with_final(data)
        enriched, _ = enrich_worlds_eliminations(data, records('B-0'))
        self.assertEqual(enriched[0]['attributes']['worlds_eliminations']['group'], [])
        self.assertEqual(enriched[0]['attributes']['worlds_eliminations']['quarterfinal'], [2018])

    def test_ongoing_event_and_future_final_do_not_prove_an_elimination(self):
        data = snapshot()
        event = '2026 Season World Championship/Main Event'
        playin = '2026 Season World Championship/Play-In'
        data['tournaments'] = [{'OverviewPage': event}, {'OverviewPage': playin}]
        add_series(data, event, 'Round 1', 1, ('A', 'C'), [1], best_of=1, date='2026-10-17')
        add_series(data, event, 'Finals', 1, ('A', 'B'), [], date='2026-11-01')
        add_series(data, playin, 'Round 2', 1, ('A', 'J'), [1, 1], date='2026-10-16')
        placed(data, 'J', year=2026)
        data['eliminations_source']['results'][0]['date'] = '2026-10-17'
        enriched, _ = enrich_worlds_eliminations(data, records('C-0', 'J-0'))
        for record in enriched:
            self.assertNotIn('worlds_eliminations', record['attributes'])
            self.assertEqual(record['attributes']['worlds_eliminations_meta']['unknown_years'], [2026])

    def test_missing_scoreboard_in_completed_main_prevents_group_inference(self):
        data = snapshot()
        add_series(data, MAIN, 'Day 1', 1, ('A', 'I'), [1], best_of=1)
        with_final(data)
        data['rows'].pop()
        enriched, report = enrich_worlds_eliminations(data, records('I-0'))
        self.assertNotIn('worlds_eliminations', enriched[0]['attributes'])
        self.assertIn(MAIN, report['incomplete_events'])

    def test_season_one_double_elimination_is_not_guessed_from_round_number(self):
        data = snapshot()
        event = 'Season 1 World Championship'
        data['tournaments'] = [{'OverviewPage': event}]
        add_series(data, event, 'Bracket Stage', 1, ('A', 'C'), [1, 1], date='2011-06-19')
        add_series(data, event, 'Finals', 1, ('A', 'E'), [1, 1], date='2011-06-20')
        enriched, report = enrich_worlds_eliminations(data, records('C-0', 'E-0'))
        self.assertNotIn('worlds_eliminations', enriched[0]['attributes'])
        self.assertEqual(enriched[1]['attributes']['worlds_eliminations']['final'], [2011])
        self.assertTrue(any(row['team'] == 'C' for row in report['unknown_teams']))

    def test_one_known_team_does_not_mark_other_unknown_team_in_same_year_complete(self):
        data = snapshot()
        add_series(data, PLAYIN, 'Round 2', 1, ('K', 'J'), [1, 1],
                   rosters={'J': ['A-0', 'J-1', 'J-2', 'J-3', 'J-4']})
        with_final(data)
        enriched, _ = enrich_worlds_eliminations(data, records('A-0'))
        self.assertFalse(enriched[0]['attributes']['worlds_eliminations_meta']['complete'])
        self.assertEqual(enriched[0]['attributes']['worlds_eliminations_meta']['unknown_years'], [2018])

    def test_alias_case_and_disambiguation_use_source_player_identity(self):
        data = snapshot()
        data['players'] = [{'page': 'FabFabulous'}, {'page': 'Duke (Other Person)'}]
        add_series(data, MAIN, 'Finals', 1, ('A', 'E'), [1, 1],
                   rosters={'E': ['fabFabulous', 'E-1', 'E-2', 'E-3', 'E-4']})
        enriched, _ = enrich_worlds_eliminations(data, records('FabFabulous', 'Duke (Other Person)'))
        self.assertEqual(enriched[0]['attributes']['worlds_eliminations']['final'], [2018])
        self.assertNotIn('worlds_eliminations_meta', enriched[1]['attributes'])

    def test_pure_enrichment_preserves_portraits_statistics_and_source(self):
        data = with_final(snapshot())
        source_records = records('E-0')
        source_records[0].update(career_stats={'worlds': {'games': 42}})
        source_records[0]['attributes']['portrait_url'] = 'https://example.org/photo.png'
        before, original = deepcopy(data), deepcopy(source_records)
        enriched, _ = enrich_worlds_eliminations(data, source_records)
        self.assertEqual(data, before)
        self.assertEqual(source_records, original)
        self.assertEqual(enriched[0]['career_stats'], original[0]['career_stats'])
        self.assertEqual(enriched[0]['attributes']['portrait_url'], 'https://example.org/photo.png')

    def test_stale_or_unchecked_placement_export_is_rejected(self):
        data = with_final(snapshot())
        placed(data, 'J')
        data['eliminations_source']['as_of'] = '2025-01-01'
        with self.assertRaisesRegex(ValueError, 'as_of'):
            enrich_worlds_eliminations(data, [])
        data['eliminations_source']['as_of'] = data['as_of']
        data['eliminations_source']['complete'] = False
        with self.assertRaisesRegex(ValueError, 'checked Leaguepedia'):
            enrich_worlds_eliminations(data, [])
