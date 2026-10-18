import copy
import unittest

from .worlds_import import build_worlds_players


PLAY_IN = '2017 Season World Championship/Play-In'
MAIN = '2017 Season World Championship/Main Event'


def snapshot(games=1):
    players = [{
        'page': f'Player {i}', 'id': f'Nick{i}', 'name': f'Real {i}',
        'country': 'South Korea', 'residency': 'LCK', 'role': 'Mid',
        'birthdate': '1996-05-07', 'retired': 'No', 'favorite_champions': ['Lux'],
    } for i in range(10)]
    aliases = [{'alias': f'Old{i}', 'page': player['page']} for i, player in enumerate(players)]
    rows = []
    roles = ['Top', 'Jungle', 'Mid', 'AD Carry', 'Support']
    for game in range(games):
        for i in range(10):
            rows.append({
                'player': f'Old{i}', 'champion': 'Ahri' if game % 2 == 0 else 'Azir',
                'win': 'Yes' if (i < 5) == (game % 2 == 0) else 'No',
                'game_id': f'Game{game}', 'date': f'2017-10-{game + 1:02} 10:00:00',
                'tournament': PLAY_IN if game == 0 else MAIN,
                'team': 'Team A' if i < 5 else 'Team B',
                'role': roles[i % 5], 'ingame_role': roles[i % 5], 'pentakills': '0',
            })
    expected = {PLAY_IN: 1}
    if games > 1:
        expected[MAIN] = games - 1
    return {'as_of': '2026-10-18T00:00:00Z', 'expected_game_counts': expected,
            'tournaments': [{'OverviewPage': PLAY_IN, 'Year': 2017}, {'OverviewPage': MAIN, 'Year': 2017}],
            'rows': rows, 'aliases': aliases, 'players': players}


class WorldsImportTests(unittest.TestCase):
    def test_aggregates_verified_games_wins_and_complete_champion_breakdown(self):
        data = snapshot(2)
        fixtures, report = build_worlds_players(data, [])
        first = next(row for row in fixtures if row['nickname'] == 'Nick0')
        stats = first['career_stats']['worlds']
        self.assertEqual((stats['games'], stats['wins'], stats['losses']), (2, 1, 1))
        self.assertTrue(stats['complete'])
        self.assertEqual(stats['scope'], 'worlds_including_play_in')
        self.assertEqual(stats['source'], 'Leaguepedia')
        self.assertEqual(stats['as_of'], data['as_of'])
        self.assertEqual(stats['champions'], [
            {'champion': 'Ahri', 'games': 1, 'wins': 1},
            {'champion': 'Azir', 'games': 1, 'wins': 0},
        ])
        self.assertEqual(report['games'], 2)
        self.assertEqual(report['confirmed_players'], 10)
        self.assertEqual(report['complete_players'], 10)
        self.assertTrue(report['coverage_verified'])
        self.assertEqual(report['expected_games'], 2)

    def test_keeps_existing_identity_other_statistics_and_verified_histories(self):
        existing = [{
            'id': 123, 'slug': 'permanent-id', 'nickname': 'OldNick',
            'attributes': {'source_page': 'Player 0', 'teams': ['Historical Team'],
                           'team_years': {'Historical Team': [2010]}, 'coaches': ['Coach'],
                           'worlds_titles': [2016], 'worlds_titles_verified': True,
                           'top_champions_career': ['Lux']},
            'career_stats': {'other_scope': {'games': 88}},
        }]
        data = snapshot(2)
        fixture = next(row for row in build_worlds_players(data, existing)[0] if row['slug'] == 'permanent-id')
        self.assertEqual(fixture['id'], 123)
        self.assertEqual(fixture['nickname'], 'Nick0')
        self.assertEqual(fixture['career_stats']['other_scope'], {'games': 88})
        attrs = fixture['attributes']
        self.assertEqual(attrs['worlds_titles'], [2016])
        self.assertTrue(attrs['worlds_titles_verified'])
        self.assertEqual(attrs['coaches'], ['Coach'])
        self.assertEqual(attrs['teams'], ['Historical Team', 'Team A'])
        self.assertEqual(attrs['team_years']['Historical Team'], [2010])
        self.assertEqual(attrs['team_years']['Team A'], [2017])
        self.assertEqual(attrs['worlds_appearances'], [2017])
        self.assertEqual(attrs['worlds_roles'], ['top'])
        self.assertTrue(attrs['worlds_verified'])
        self.assertNotIn('top_champions_career', attrs)
        self.assertEqual(attrs['favorite_champions'], ['Lux'])

    def test_reuses_only_an_unambiguous_canonical_page_slug(self):
        existing = [{'id': 7, 'slug': 'player-0', 'nickname': 'Something else', 'attributes': {}}]
        rows, _ = build_worlds_players(snapshot(), existing)
        row = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertEqual((row['id'], row['slug']), (7, 'player-0'))

    def test_two_distinct_pages_with_the_same_nickname_are_not_merged(self):
        data = snapshot()
        data['players'][0]['id'] = data['players'][1]['id'] = 'Shared nickname'
        rows, _ = build_worlds_players(data, [{'id': 44, 'slug': 'shared-nickname', 'nickname': 'Shared nickname'}])
        confirmed = [row for row in rows if row['attributes']['worlds_verified']]
        self.assertEqual(len(confirmed), 10)
        self.assertEqual(len({row['slug'] for row in rows}), 11)
        old = next(row for row in rows if row.get('id') == 44)
        self.assertFalse(old['attributes']['worlds_verified'])

    def test_slug_collisions_and_non_ascii_names_get_stable_distinct_slugs(self):
        data = snapshot()
        for index, page in [(0, 'Café'), (1, 'Cafe')]:
            data['players'][index]['page'] = page
            data['aliases'][index]['page'] = page
        first, _ = build_worlds_players(data, [])
        second, _ = build_worlds_players(data, [])
        self.assertEqual(first, second)
        self.assertEqual(len({row['slug'] for row in first}), 10)
        self.assertTrue(all(row['slug'].isascii() and len(row['slug']) <= 80 for row in first))

    def test_ambiguous_canonical_slugs_cannot_claim_an_existing_identity(self):
        data = snapshot()
        data['players'][0]['page'] = data['aliases'][0]['page'] = 'Cafe'
        data['players'].append({**data['players'][0], 'page': 'Café', 'id': 'Another person'})
        rows, _ = build_worlds_players(data, [{'id': 7, 'slug': 'cafe', 'nickname': 'Historical nickname'}])
        old = next(row for row in rows if row.get('id') == 7)
        imported = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertFalse(old['attributes']['worlds_verified'])
        self.assertNotEqual(imported['slug'], old['slug'])
        self.assertNotIn('id', imported)

    def test_preserves_records_outside_confirmed_worlds_but_marks_them_unverified(self):
        existing = [{'id': 99, 'slug': 'bench-only', 'nickname': 'Bench', 'worlds_count': 4,
                     'attributes': {'worlds_appearances': [2018], 'worlds_titles': [2018], 'coaches': ['Known']},
                     'career_stats': {'worlds': {'complete': True, 'games': 4}, 'other': {'games': 2}}}]
        rows, report = build_worlds_players(snapshot(), existing)
        old = next(row for row in rows if row['slug'] == 'bench-only')
        self.assertEqual(old['id'], 99)
        self.assertFalse(old['attributes']['worlds_verified'])
        self.assertEqual(old['worlds_count'], 0)
        self.assertEqual(old['attributes']['worlds_appearances'], [])
        self.assertEqual(old['attributes']['worlds_titles'], [2018])
        self.assertEqual(old['attributes']['coaches'], ['Known'])
        self.assertFalse(old['career_stats']['worlds']['complete'])
        self.assertEqual(report['preserved_unverified_players'], 1)

    def test_duplicate_rows_are_counted_once_and_inputs_are_never_mutated(self):
        data = snapshot()
        data['rows'].append(copy.deepcopy(data['rows'][0]))
        existing = [{'id': 1, 'slug': 'player-0', 'attributes': {'teams': ['Old']}}]
        original = copy.deepcopy((data, existing))
        rows, report = build_worlds_players(data, existing)
        self.assertEqual(report['duplicate_rows'], 1)
        self.assertEqual(report['unique_rows'], 10)
        self.assertEqual(next(row for row in rows if row['slug'] == 'player-0')['career_stats']['worlds']['games'], 1)
        self.assertEqual((data, existing), original)
        refreshed, second_report = build_worlds_players(data, rows)
        self.assertEqual(refreshed, rows)
        self.assertEqual(second_report['new_players'], 0)

    def test_conflicting_duplicate_rows_fail_closed(self):
        for field, value in [('champion', 'Lux'), ('win', 'No'), ('team', 'Other team'), ('date', '2017-10-02 10:00:00')]:
            data = snapshot()
            duplicate = {**data['rows'][0], field: value}
            data['rows'].append(duplicate)
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_worlds_players(data, [])

    def test_unknown_alias_does_not_fall_back_to_a_nickname(self):
        data = snapshot()
        data['rows'][0]['player'] = 'Nick0'
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])

    def test_a_canonical_page_itself_does_not_require_a_redundant_alias(self):
        data = snapshot()
        data['rows'][0]['player'] = 'Player 0'
        data['aliases'] = data['aliases'][1:]
        rows, _ = build_worlds_players(data, [])
        self.assertEqual(len(rows), 10)

    def test_aliases_are_nfkc_case_insensitive_without_merging_disambiguated_pages(self):
        data = snapshot()
        data['aliases'][0] = {'alias': 'ＯＬＤ０', 'page': 'PLAYER_0'}
        data['rows'][0]['player'] = 'old0'
        data['players'].append(copy.deepcopy(data['players'][0]))
        rows, _ = build_worlds_players(data, [])
        self.assertEqual(next(row for row in rows if row['nickname'] == 'Nick0')['attributes']['leaguepedia_page'], 'Player 0')
        data['aliases'].append({'alias': 'old0', 'page': 'Player 1'})
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])

    def test_ambiguous_aliases_and_existing_source_identities_fail_closed(self):
        data = snapshot()
        data['aliases'].append({'alias': 'Old0', 'page': 'Player 1'})
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])
        existing = [{'id': i, 'slug': f'old-{i}', 'attributes': {'leaguepedia_page': 'Player 0'}} for i in range(2)]
        with self.assertRaises(ValueError):
            build_worlds_players(snapshot(), existing)

    def test_unknown_tournaments_and_future_or_equal_cutoff_rows_fail_closed(self):
        for field, value in [('tournament', '2023 Worlds Qualifying Series'),
                             ('date', '2026-10-18T00:00:00Z'), ('date', '2026-10-19 00:00:00'),
                             ('date', ''), ('game_id', ''), ('champion', ''), ('win', 'maybe')]:
            data = snapshot()
            data['rows'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                build_worlds_players(data, [])

    def test_as_of_cutoff_is_strict_and_timezone_aware(self):
        data = snapshot()
        data['as_of'] = '2017-10-01T12:00:00+02:00'
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])
        data['as_of'] = '2017-10-01T12:00:01+02:00'
        self.assertEqual(build_worlds_players(data, [])[1]['games'], 1)

    def test_partial_or_internally_inconsistent_games_fail_closed(self):
        variants = []
        missing = snapshot(); missing['rows'].pop(); variants.append(missing)
        bad_winners = snapshot(); bad_winners['rows'][0]['win'] = 'No'; variants.append(bad_winners)
        split_winners = snapshot(); split_winners['rows'][0]['win'] = 'No'; split_winners['rows'][5]['win'] = 'Yes'; variants.append(split_winners)
        third_team = snapshot(); third_team['rows'][0]['team'] = 'Third'; variants.append(third_team)
        bad_teams = snapshot(); bad_teams['rows'][4]['team'] = 'Team B'; variants.append(bad_teams)
        mixed_tournaments = snapshot(); mixed_tournaments['rows'][0]['tournament'] = MAIN; variants.append(mixed_tournaments)
        for data in variants:
            with self.subTest(rows=data['rows']), self.assertRaises(ValueError):
                build_worlds_players(data, [])

    def test_playin_participation_is_distinct_from_advancing_to_main_event(self):
        playin_only, _ = build_worlds_players(snapshot(), [])
        attrs = playin_only[0]['attributes']
        self.assertEqual(attrs['worlds_playin_appearances'], [2017])
        self.assertEqual(attrs['worlds_playin'], [])
        both, _ = build_worlds_players(snapshot(2), [])
        self.assertEqual(both[0]['attributes']['worlds_playin'], [2017])
        changed_team = snapshot(2)
        for row in changed_team['rows'][10:]:
            row['team'] = 'Different ' + row['team']
        rows, _ = build_worlds_players(changed_team, [])
        self.assertEqual(rows[0]['attributes']['worlds_playin_appearances'], [2017])
        self.assertEqual(rows[0]['attributes']['worlds_playin'], [])

    def test_metadata_is_normalized_without_guessed_country_or_activity(self):
        data = snapshot()
        data['players'][0].update(country='Denmark', residency='LEC', birthdate='1999-11-17', retired='Yes', name='A&amp;nbsp;B')
        data['players'][1].update(country='Unknown place', residency='', birthdate=None, retired=None)
        rows, report = build_worlds_players(data, [])
        known = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertEqual((known['country_code'], known['continent'], known['birth_year'], known['is_active']), ('DK', 'Europe', 1999, False))
        self.assertEqual(known['real_name'], 'A B')
        unknown = next(row for row in rows if row['nickname'] == 'Nick1')
        self.assertEqual((unknown['country_code'], unknown['residency'], unknown['birth_year']), ('', '', None))
        self.assertFalse(unknown['attributes']['activity_verified'])
        self.assertIn('Player 1', report['unknown_metadata']['country'])

    def test_primary_nationality_takes_precedence_over_country_of_birth(self):
        data = snapshot()
        data['players'][0].update(country='South Korea', nationality_primary='United States')
        data['players'][1].update(country='South Korea', NationalityPrimary='Unknown place')
        rows, report = build_worlds_players(data, [])
        citizen = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertEqual((citizen['country_code'], citizen['continent']), ('US', 'North America'))
        self.assertEqual(citizen['attributes']['leaguepedia_country_of_birth'], 'South Korea')
        self.assertEqual(citizen['attributes']['leaguepedia_nationality_primary'], 'United States')
        unknown = next(row for row in rows if row['nickname'] == 'Nick1')
        self.assertEqual(unknown['country_code'], '')
        self.assertIn('Player 1', report['unknown_metadata']['country'])

    def test_pentakills_are_only_declared_complete_when_every_game_has_a_value(self):
        data = snapshot(2)
        data['rows'][0]['pentakills'] = '1'
        rows, _ = build_worlds_players(data, [])
        player = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertEqual(player['attributes']['pentakills_worlds'], 1)
        data['rows'][10]['pentakills'] = None
        rows, _ = build_worlds_players(data, [])
        player = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertNotIn('pentakills_worlds', player['attributes'])

    def test_python_repr_favorites_are_safely_separate_from_played_champions(self):
        data = snapshot()
        data['players'][0]['favorite_champions'] = "['Jayce', 'Lux', 'Jayce']"
        rows, _ = build_worlds_players(data, [])
        player = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertEqual(player['attributes']['favorite_champions'], ['Jayce', 'Lux'])
        self.assertEqual(player['career_stats']['worlds']['champions'], [{'champion': 'Ahri', 'games': 1, 'wins': 1}])
        self.assertNotIn('top_champions_career', player['attributes'])
        data['players'][0]['favorite_champions'] = "[__import__('os').getcwd()]"
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])

    def test_broad_residency_does_not_imply_a_league_or_replace_verified_history(self):
        data = snapshot()
        data['players'][0]['residency'] = 'Americas'
        data['players'][1]['residency'] = 'EMEA'
        existing = [{'slug': 'player-0', 'residency': 'LCS', 'attributes': {'leagues': ['LCS', 'LEC']}}]
        rows, report = build_worlds_players(data, existing)
        known = next(row for row in rows if row['nickname'] == 'Nick0')
        self.assertEqual(known['residency'], 'LCS')
        self.assertEqual(known['attributes']['leagues'], ['LCS', 'LEC'])
        self.assertEqual(known['attributes']['leaguepedia_residency'], 'Americas')
        new = next(row for row in rows if row['nickname'] == 'Nick1')
        self.assertEqual(new['residency'], '')
        self.assertEqual(new['attributes']['leaguepedia_residency'], 'EMEA')
        self.assertNotIn('residency', report['unknown_metadata'])

    def test_missing_metadata_is_reported_and_never_inferred_from_nickname(self):
        data = snapshot()
        data['players'] = data['players'][1:]
        rows, report = build_worlds_players(data, [])
        player = next(row for row in rows if row['slug'] == 'player-0')
        self.assertEqual(player['country_code'], '')
        self.assertEqual(player['residency'], '')
        self.assertIsNone(player['birth_year'])
        self.assertFalse(player['attributes']['activity_verified'])
        self.assertEqual(player['primary_role'], 'top')
        self.assertEqual(report['metadata_missing_pages'], ['Player 0'])

    def test_null_optional_existing_json_is_normalized_but_malformed_json_is_rejected(self):
        rows, _ = build_worlds_players(snapshot(), [{'slug': 'player-0', 'attributes': None, 'career_stats': None}])
        self.assertTrue(next(row for row in rows if row['slug'] == 'player-0')['career_stats']['worlds']['complete'])
        with self.assertRaises(ValueError):
            build_worlds_players(snapshot(), [{'slug': 'player-0', 'attributes': []}])

    def test_empty_or_mis_scoped_snapshots_are_not_complete_imports(self):
        data = snapshot(); data['rows'] = []
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])
        data = snapshot(); data['tournaments'][0] = {'OverviewPage': '2023 Worlds Qualifying Series', 'Year': 2023}
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])

    def test_independent_coverage_is_mandatory_for_every_tournament_with_rows(self):
        for coverage in (None, {}, {PLAY_IN: 1}):
            data = snapshot(2)
            data['expected_game_counts'] = coverage
            with self.subTest(coverage=coverage), self.assertRaises(ValueError):
                build_worlds_players(data, [])
        data = snapshot()
        del data['expected_game_counts']
        with self.assertRaises(ValueError):
            build_worlds_players(data, [])

    def test_coverage_detects_a_missing_whole_game_or_entire_series(self):
        for rows in (20, 10):
            data = snapshot(3)
            data['rows'] = data['rows'][:rows]
            with self.subTest(remaining_rows=rows), self.assertRaisesRegex(ValueError, 'coverage mismatch'):
                build_worlds_players(data, [])

    def test_future_catalog_events_need_no_count_but_all_supplied_counts_are_checked(self):
        data = snapshot()
        data['tournaments'].append({'OverviewPage': '2027 Season World Championship/Main Event', 'Year': 2027})
        self.assertNotIn(MAIN, data['expected_game_counts'])
        self.assertEqual(build_worlds_players(data, [])[1]['games'], 1)
        data['expected_game_counts'][MAIN] = 0
        self.assertEqual(build_worlds_players(data, [])[1]['expected_games'], 1)
        for coverage in ({PLAY_IN: 0}, {PLAY_IN: 2}, {PLAY_IN: -1}, {PLAY_IN: True},
                         {PLAY_IN: '1'}, {PLAY_IN: 1.0}, {PLAY_IN: 1, 'Other': 0}):
            data['expected_game_counts'] = coverage
            with self.subTest(coverage=coverage), self.assertRaises(ValueError):
                build_worlds_players(data, [])
