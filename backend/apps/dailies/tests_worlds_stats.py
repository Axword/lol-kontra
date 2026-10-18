import copy
import unittest
from decimal import Decimal

from .tests_validators import FakeCondition, FakePlayer, FakeSlot
from .validators import PlayerFacts, evaluate_condition, explain_slot_match, player_matches_slot


def worlds_stats(games=100, wins=50, **extra):
    return {
        'games': games, 'wins': wins, 'losses': games - wins,
        'complete': True, 'scope': 'worlds_including_play_in', 'source': 'Leaguepedia',
        **extra,
    }


def player_with(stats):
    player = FakePlayer()
    player.career_stats = {'worlds': stats}
    return player


def champion_stats(rows):
    champions = [{'champion': name, 'games': games, 'wins': games // 2} for name, games in rows]
    return worlds_stats(sum(row['games'] for row in champions), sum(row['wins'] for row in champions),
                        champions=champions)


class WorldsRateTests(unittest.TestCase):
    def test_win_rate_strict_and_inclusive_fifty_percent_boundaries(self):
        for wins in [49, 50, 51]:
            player = player_with(worlds_stats(wins=wins))
            for operator, expected in [('gt', wins > 50), ('lt', wins < 50),
                                       ('gte', wins >= 50), ('lte', wins <= 50), ('eq', wins == 50)]:
                with self.subTest(wins=wins, operator=operator):
                    self.assertEqual(evaluate_condition(player, 'worlds_win_rate', operator, 50), expected)

    def test_rate_compares_raw_counters_without_rounding(self):
        almost_equal = player_with(worlds_stats(games=1000001, wins=500001))
        self.assertTrue(evaluate_condition(almost_equal, 'worlds_win_rate', 'gt', 50))
        self.assertFalse(evaluate_condition(almost_equal, 'worlds_win_rate', 'eq', 50))
        third = player_with(worlds_stats(games=3, wins=1))
        self.assertTrue(evaluate_condition(third, 'worlds_win_rate', 'gt', '33.333333333333333333333333333333333333'))
        self.assertTrue(evaluate_condition(third, 'worlds_win_rate', 'lt', '33.333333333333333333333333333333333334'))
        self.assertTrue(evaluate_condition(player_with(worlds_stats()), 'worlds_win_rate', 'eq', Decimal('50.000')))

    def test_zero_and_one_hundred_are_real_rates_only_for_known_games(self):
        self.assertTrue(evaluate_condition(player_with(worlds_stats(10, 0)), 'worlds_win_rate', 'eq', 0))
        self.assertTrue(evaluate_condition(player_with(worlds_stats(10, 10)), 'worlds_win_rate', 'eq', 100))
        self.assertFalse(evaluate_condition(player_with(worlds_stats(0, 0)), 'worlds_win_rate', 'eq', 0))

    def test_invalid_rate_thresholds_and_operators_fail_closed(self):
        player = player_with(worlds_stats())
        for threshold in [-1, 101, None, True, False, [], {}, 'NaN', 'Infinity', 'bad']:
            with self.subTest(threshold=threshold):
                self.assertFalse(evaluate_condition(player, 'worlds_win_rate', 'gte', threshold))
        for operator in ['in', 'any', 'greater', 'neq']:
            self.assertFalse(evaluate_condition(player, 'worlds_win_rate', operator, 50))


class WorldsGamesTests(unittest.TestCase):
    def test_games_strict_and_inclusive_boundaries(self):
        for games in [19, 20, 21]:
            player = player_with(worlds_stats(games, 10))
            for operator, expected in [('gt', games > 20), ('lt', games < 20),
                                       ('gte', games >= 20), ('lte', games <= 20), ('eq', games == 20)]:
                with self.subTest(games=games, operator=operator):
                    self.assertEqual(evaluate_condition(player, 'worlds_games', operator, 20), expected)

    def test_zero_threshold_does_not_convert_missing_games_to_zero(self):
        self.assertTrue(evaluate_condition(player_with(worlds_stats(1, 0)), 'worlds_games', 'gt', 0))
        for stats in [None, worlds_stats(0, 0)]:
            self.assertFalse(evaluate_condition(player_with(stats), 'worlds_games', 'eq', 0))
            self.assertFalse(evaluate_condition(player_with(stats), 'worlds_games', 'lt', 100))

    def test_invalid_game_thresholds_and_operators_fail_closed(self):
        player = player_with(worlds_stats())
        for threshold in [-1, None, True, False, 'bad', {}, [], float('nan'), float('inf')]:
            with self.subTest(threshold=threshold):
                self.assertFalse(evaluate_condition(player, 'worlds_games', 'gt', threshold))
        for operator in ['in', 'any', 'greater', 'neq']:
            self.assertFalse(evaluate_condition(player, 'worlds_games', operator, 20))


class WorldsDataValidationTests(unittest.TestCase):
    def assert_unknown(self, stats):
        player = player_with(stats)
        self.assertFalse(evaluate_condition(player, 'worlds_win_rate', 'lt', 100))
        self.assertFalse(evaluate_condition(player, 'worlds_games', 'lt', 1000))
        self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Ahri'))

    def test_missing_career_or_worlds_data_never_matches(self):
        self.assert_unknown(None)
        self.assert_unknown([])
        self.assert_unknown({})
        player = FakePlayer(attributes={'games': 100, 'wins': 50, 'worlds_games': 100})
        self.assertFalse(evaluate_condition(player, 'worlds_games', 'gt', 0))
        for career in [None, [], 'unknown', {}]:
            player.career_stats = career
            self.assertFalse(evaluate_condition(player, 'worlds_win_rate', 'lt', 100))

    def test_incomplete_or_wrong_scope_never_matches(self):
        for value in [False, None, 1, 'true']:
            with self.subTest(complete=value):
                self.assert_unknown(worlds_stats(complete=value))
        for scope in [None, '', 'worlds_main_event', 'career']:
            self.assert_unknown(worlds_stats(scope=scope))
        for missing in ['complete', 'scope', 'games', 'wins', 'losses']:
            stats = worlds_stats()
            del stats[missing]
            self.assert_unknown(stats)

    def test_totals_require_consistent_nonnegative_integers_without_bools(self):
        for field in ['games', 'wins', 'losses']:
            for value in [-1, None, True, False, '50', 50.0, [], {}]:
                with self.subTest(field=field, value=value):
                    stats = worlds_stats()
                    stats[field] = value
                    self.assert_unknown(stats)
        self.assert_unknown(worlds_stats(losses=49))
        self.assert_unknown(worlds_stats(wins=101))

    def test_explicitly_unverified_player_cannot_fill_an_otherwise_valid_slot(self):
        player = player_with(worlds_stats())
        player.attributes = {'worlds_verified': False}
        slot = FakeSlot('mid', [FakeCondition('country', 'eq', 'KR')])
        self.assertFalse(evaluate_condition(player, 'country', 'eq', 'KR'))
        self.assertFalse(evaluate_condition(player, 'worlds_games', 'gt', 0))
        self.assertFalse(player_matches_slot(player, slot))
        explanation = explain_slot_match(player, slot)
        self.assertFalse(explanation['matched'])
        verification = next(check for check in explanation['checks'] if check['condition'] == 'worlds_verified')
        self.assertFalse(verification['passed'])

    def test_missing_or_true_verification_preserves_existing_valid_players(self):
        slot = FakeSlot('mid', [FakeCondition('country', 'eq', 'KR')])
        for attributes in [{}, {'worlds_verified': True}]:
            player = player_with(worlds_stats())
            player.attributes = attributes
            self.assertTrue(player_matches_slot(player, slot))
            self.assertTrue(explain_slot_match(player, slot)['matched'])

    def test_explicit_final_list_distinguishes_title_roster_from_actual_final(self):
        duke = FakePlayer(attributes={'worlds_titles': [2018], 'worlds_finals': []})
        self.assertTrue(evaluate_condition(duke, 'worlds_champion', 'eq', True))
        self.assertFalse(evaluate_condition(duke, 'worlds_final', 'eq', True))
        legacy = FakePlayer(attributes={'worlds_titles': [2018]})
        self.assertTrue(evaluate_condition(legacy, 'worlds_final', 'eq', True))

    def test_explicit_group_escape_list_distinguishes_knockout_byes(self):
        bye = FakePlayer(attributes={'worlds_group_escapes': [], 'worlds_semifinals': [2012], 'worlds_titles': [2012]})
        self.assertFalse(evaluate_condition(bye, 'worlds_group_escape', 'eq', True))
        legacy = FakePlayer(attributes={'worlds_semifinals': [2012], 'worlds_titles': [2012]})
        self.assertTrue(evaluate_condition(legacy, 'worlds_group_escape', 'eq', True))

    def test_champion_played_uses_real_worlds_games_including_outside_top_five(self):
        player = player_with(champion_stats([
            ('Ahri', 10), ('Ryze', 9), ('Azir', 8), ('Orianna', 7), ('Viktor', 6), ('Lux', 1), ('Anivia', 0),
        ]))
        player.attributes = {'top_champions_career': [{'champion': 'Akali'}]}
        self.assertTrue(evaluate_condition(player, 'champion_played', 'eq', 'Lux'))
        self.assertTrue(evaluate_condition(player, 'champion_played', 'in', ['Akali', 'Lux']))
        self.assertFalse(evaluate_condition(player, 'champion_played', 'eq', 'Akali'))
        self.assertFalse(evaluate_condition(player, 'champion_played', 'eq', 'Anivia'))
        self.assertFalse(evaluate_condition(player, 'champion_played', 'neq', 'Akali'))

    def test_invalid_new_champion_data_never_falls_back_to_favourites(self):
        for stats in [None, worlds_stats(complete=False), worlds_stats()]:
            player = player_with(stats)
            player.attributes = {'top_champions_career': [{'champion': 'Ahri'}]}
            self.assertFalse(evaluate_condition(player, 'champion_played', 'eq', 'Ahri'))
        legacy = FakePlayer(attributes={'top_champions_career': [{'champion': 'Ahri'}]})
        self.assertTrue(evaluate_condition(legacy, 'champion_played', 'eq', 'Ahri'))


class WorldsTopFiveTests(unittest.TestCase):
    def test_top_five_includes_all_champions_tied_for_fifth(self):
        player = player_with(champion_stats([
            ('Ahri', 10), ('Ryze', 9), ('Azir', 8), ('Orianna', 7),
            ('Viktor', 6), ('Syndra', 6), ('Anivia', 1), ('Lux', 0),
        ]))
        self.assertEqual(set(PlayerFacts(player).worlds_top5_champions),
                         {'Ahri', 'Ryze', 'Azir', 'Orianna', 'Viktor', 'Syndra'})
        self.assertTrue(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Syndra'))
        self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Anivia'))
        self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Lux'))

    def test_fewer_than_five_accepts_all_played_champions_and_never_zero_games(self):
        player = player_with(champion_stats([('Ahri', 2), ('Ryze', 1), ('Lux', 0)]))
        self.assertTrue(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Ahri'))
        self.assertTrue(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Ryze'))
        self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Lux'))

    def test_top_five_sorts_games_instead_of_trusting_input_order(self):
        player = player_with(champion_stats([
            ('Lux', 1), ('Ahri', 10), ('Ryze', 9), ('Azir', 8), ('Orianna', 7), ('Viktor', 6),
        ]))
        self.assertTrue(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Viktor'))
        self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Lux'))

    def test_names_ignore_case_and_standard_punctuation_without_substring_matches(self):
        for stored, query in [("Cho’Gath", "cho'gath"), ('Lee Sin', 'leesin'),
                              ('Dr. Mundo', 'DR MUNDO'), ("Kai'Sa", 'kaisa')]:
            with self.subTest(stored=stored, query=query):
                self.assertTrue(evaluate_condition(player_with(champion_stats([(stored, 5)])),
                                                   'worlds_top5_champion', 'eq', query))
        player = player_with(champion_stats([('Viego', 5), ('Aurelion Sol', 3), ('Wukong', 1)]))
        for query in ['Vi', 'Aurelion', 'Monkey King', 'Viego!', None, True, {}, []]:
            with self.subTest(query=query):
                self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', query))

    def test_invalid_breakdown_does_not_prove_a_top_five_champion(self):
        valid = champion_stats([('Ahri', 5)])
        malformed = [None, [], {}, [{'champion': 'Ahri', 'games': 4, 'wins': 2}],
                     [{'champion': 'Ahri', 'games': True, 'wins': 0}],
                     [{'champion': 'Ahri', 'games': -5, 'wins': 0}],
                     [{'champion': 'Ahri', 'games': 5, 'wins': 6}],
                     [{'champion': 'Ahri', 'games': 5}],
                     [{'champion': '', 'games': 5, 'wins': 2}],
                     [{'champion': 'Ahri!', 'games': 5, 'wins': 2}],
                     [{'champion': 'Ahri', 'games': 3, 'wins': 1}, {'champion': 'AHRI', 'games': 2, 'wins': 1}]]
        for rows in malformed:
            with self.subTest(champions=rows):
                stats = copy.deepcopy(valid)
                stats['champions'] = rows
                self.assertFalse(evaluate_condition(player_with(stats), 'worlds_top5_champion', 'eq', 'Ahri'))
        del valid['champions']
        self.assertFalse(evaluate_condition(player_with(valid), 'worlds_top5_champion', 'eq', 'Ahri'))

    def test_top_five_only_accepts_eq_and_worlds_data(self):
        player = player_with(champion_stats([('Ahri', 5)]))
        player.attributes = {'top_champions_career': [{'champion': 'Lux'}]}
        self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', 'eq', 'Lux'))
        for operator in ['in', 'any', 'gt', 'gte', 'lt', 'lte']:
            self.assertFalse(evaluate_condition(player, 'worlds_top5_champion', operator, 'Ahri'))

    def test_new_conditions_keep_the_existing_role_requirement(self):
        player = player_with(champion_stats([('Ahri', 6)]))
        conditions = [FakeCondition('worlds_win_rate', 'gte', 50),
                      FakeCondition('worlds_games', 'gt', 5),
                      FakeCondition('worlds_top5_champion', 'eq', 'Ahri')]
        self.assertTrue(player_matches_slot(player, FakeSlot('mid', conditions)))
        self.assertFalse(player_matches_slot(player, FakeSlot('top', conditions)))


if __name__ == '__main__':
    unittest.main()
