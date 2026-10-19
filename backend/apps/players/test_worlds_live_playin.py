"""A completed Play-In can resolve while the main Worlds event is ongoing."""
from copy import deepcopy
import unittest

from .test_worlds_achievements import add_series, records, snapshot
from .worlds_achievements import enrich_worlds_achievements
from .worlds_eliminations import enrich_worlds_eliminations


PLAYIN = '2026 Season World Championship/Play-In'
MAIN = '2026 Season World Championship/Main Event'


def completed_playin():
    data = snapshot()
    data['as_of'] = '2026-10-19T07:18:52+00:00'
    data['tournaments'] = [{'OverviewPage': PLAYIN}, {'OverviewPage': MAIN}]
    for stage, number, teams, wins, date in [
        ('Round 1', 1, ('C9', 'KC'), [1, 1, 2, 2, 2], '2026-10-15T18:00:00'),
        ('Round 1', 2, ('FUR', 'MVK'), [2, 2, 2], '2026-10-15T23:00:00'),
        ('Round 2', 1, ('MVK', 'KC'), [2, 2, 2], '2026-10-16T18:00:00'),
        ('Round 1', 3, ('FUR', 'C9'), [1, 1, 1, 2], '2026-10-16T23:00:00'),
        ('Round 2', 2, ('MVK', 'FUR'), [1, 1, 1, 2], '2026-10-17T18:00:00'),
        ('Round 3', 1, ('KC', 'MVK'), [1, 1, 1], '2026-10-18T18:00:00'),
    ]:
        add_series(data, PLAYIN, stage, number, teams, wins, best_of=5, date=date)
    data['eliminations_source'] = {
        'source': 'Leaguepedia', 'complete': True, 'as_of': data['as_of'],
        'results': [{'tournament': '2026 Season World Championship', 'team': team,
                     'place_number': place, 'qualified': 0, 'date': date}
                    for team, place, date in [('MVK', 17, '2026-10-18'), ('FUR', 18, '2026-10-17'),
                                              ('C9', 19, '2026-10-16')]],
    }
    data['playin_rules'] = {'2026': {
        'source': 'Riot Games', 'source_url': 'https://lolesports.com/en-US/tournament/115660540725177488/overview',
        'source_sha256': 'a' * 64, 'as_of': data['as_of'], 'participants': 4,
        'qualifying_teams': 1, 'best_of': 5, 'format': 'double_elimination',
    }}
    return data


class LiveWorldsPlayInTests(unittest.TestCase):
    def test_pinned_rules_and_completed_bracket_prove_advancement_before_main_appearance(self):
        data = completed_playin()
        enriched, report = enrich_worlds_achievements(data, records('KC-0', 'MVK-0'))
        self.assertEqual(enriched[0]['attributes']['worlds_playin'], [2026])
        self.assertEqual(enriched[1]['attributes']['worlds_playin'], [])
        for record in enriched:
            self.assertTrue(record['attributes']['worlds_achievements']['complete_fields']['worlds_playin'])
            self.assertNotIn('worlds_titles', record['attributes'])
            self.assertNotIn('worlds_finals', record['attributes'])
        self.assertEqual(report['confirmed_playin_outcomes'][0]['winner'], 'KC')

    def test_official_playin_exits_are_known_while_advancing_team_elimination_stays_unknown(self):
        enriched, report = enrich_worlds_eliminations(completed_playin(), records('KC-0', 'MVK-0', 'C9-0', 'FUR-0'))
        self.assertNotIn('worlds_eliminations', enriched[0]['attributes'])
        self.assertFalse(enriched[0]['attributes']['worlds_eliminations_meta']['complete'])
        for record in enriched[1:]:
            self.assertEqual(record['attributes']['worlds_eliminations']['play_in'], [2026])
            self.assertTrue(record['attributes']['worlds_eliminations_meta']['complete'])
        self.assertEqual(sum(row['stage'] == 'play_in' for row in report['evidence']), 3)

    def test_missing_rule_or_any_final_placement_keeps_outcome_unknown(self):
        for missing in ('rule', 'placement'):
            data = completed_playin()
            if missing == 'rule':
                data.pop('playin_rules')
            else:
                data['eliminations_source']['results'].pop()
            enriched, report = enrich_worlds_achievements(data, records('KC-0'))
            self.assertNotIn('worlds_playin', enriched[0]['attributes'])
            self.assertEqual(report['confirmed_playin_outcomes'], [])

    def test_early_win_or_loss_never_proves_final_qualification(self):
        data = completed_playin()
        data['rows'] = [row for row in data['rows'] if '_Round 3_' not in row['game_id']]
        data['achievements_source']['schedule'][-1].update(score1=0, score2=0, winner=None)
        enriched, report = enrich_worlds_achievements(data, records('KC-0', 'MVK-0'))
        self.assertEqual(report['confirmed_playin_outcomes'], [])
        for record in enriched:
            self.assertNotIn('worlds_playin', record['attributes'])

    def test_future_result_missing_scoreboard_or_conflicting_placement_is_rejected(self):
        for invalid in ('future', 'scoreboard', 'conflict'):
            data = completed_playin()
            if invalid == 'future':
                data['eliminations_source']['results'][0]['date'] = '2026-10-20'
            elif invalid == 'scoreboard':
                data['rows'].pop()
            else:
                other = deepcopy(data['eliminations_source']['results'][0])
                other['qualified'] = 1
                data['eliminations_source']['results'].append(other)
            enriched, report = enrich_worlds_achievements(data, records('KC-0'))
            self.assertEqual(report['confirmed_playin_outcomes'], [])
            self.assertNotIn('worlds_playin', enriched[0]['attributes'])

    def test_unchecked_stale_or_nonofficial_rule_source_is_rejected(self):
        for field, value in [('source', 'Unknown'), ('source_url', 'https://example.org/rules'),
                             ('source_sha256', ''), ('as_of', '2026-10-18T00:00:00Z'),
                             ('qualifying_teams', 2), ('format', 'single_elimination')]:
            data = completed_playin()
            data['playin_rules']['2026'][field] = value
            _, report = enrich_worlds_achievements(data, records('KC-0'))
            self.assertEqual(report['confirmed_playin_outcomes'], [], field)

    def test_live_enrichment_is_pure_and_keeps_prior_player_history(self):
        data, original_records = completed_playin(), records('KC-0')
        original_records[0]['attributes']['portrait_url'] = 'https://example.org/photo.png'
        original_records[0]['career_stats'] = {'career': {'games': 123}}
        before, originals = deepcopy(data), deepcopy(original_records)
        enrich_worlds_achievements(data, original_records)
        enriched, _ = enrich_worlds_eliminations(data, original_records)
        self.assertEqual(data, before)
        self.assertEqual(original_records, originals)
        self.assertEqual(enriched[0]['career_stats'], originals[0]['career_stats'])
