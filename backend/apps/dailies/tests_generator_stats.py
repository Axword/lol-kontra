from datetime import date, timedelta
import random
from unittest.mock import patch

from django.test import TestCase

from apps.players.models import Player
from . import generator
from .models import Daily, DailySlot, DailySlotCondition
from .validators import evaluate_condition


def worlds_stats(games=30, wins=20, champion='Azir', complete=True):
    return {'worlds': {
        'games': games, 'wins': wins, 'losses': games - wins,
        'champions': [{'champion': champion, 'games': games, 'wins': wins}],
        'complete': complete, 'scope': 'worlds_including_play_in', 'source': 'Leaguepedia',
    }}


class StatisticalConditionPoolTests(TestCase):
    def make_players(self, role='mid', count=20, **overrides):
        players = []
        for index in range(count):
            defaults = {
                'slug': f'{role}-{index}', 'nickname': f'{role}-{index}',
                'primary_role': role, 'country_code': 'KR', 'residency': 'LCK',
                'birth_year': 1996, 'career_stats': worlds_stats(),
                'attributes': {'worlds_appearances': [2013, 2018, 2020], 'teams': ['t1']},
            }
            defaults.update(overrides)
            players.append(Player.objects.create(**defaults))
        return players

    def stat_conditions(self, players):
        return [condition for condition in generator.build_condition_pool(players)
                if condition[2] in generator.STAT_THEMES]

    def test_complete_stats_add_supported_nonempty_conditions(self):
        players = self.make_players()
        conditions = self.stat_conditions(players)
        self.assertEqual({condition[2] for condition in conditions}, {
            'worlds_win_rate', 'worlds_games', 'worlds_top5_champion',
        })
        self.assertIn(('worlds_win_rate', 'gt', 50), {(c[2], c[3], c[4]) for c in conditions})
        self.assertIn(('worlds_games', 'gt', 25), {(c[2], c[3], c[4]) for c in conditions})
        self.assertIn(('worlds_top5_champion', 'eq', 'Azir'), {(c[2], c[3], c[4]) for c in conditions})
        for condition in conditions:
            self.assertGreaterEqual(sum(evaluate_condition(player, *condition[2:5]) for player in players),
                                    generator.MIN_CANDIDATES)

    def test_unknown_or_incomplete_stats_do_not_activate_conditions(self):
        players = self.make_players(career_stats=worlds_stats(complete=False))
        self.assertEqual(self.stat_conditions(players), [])
        for player in players:
            player.career_stats = {}
        self.assertEqual(self.stat_conditions(players), [])

    def test_unknown_players_never_match_statistical_slot(self):
        known = self.make_players()
        unknown = self.make_players(role='adc', primary_role='mid', career_stats={})
        for condition in self.stat_conditions(known + unknown):
            matching = generator._candidates_for_conditions('mid', [condition], known + unknown)
            self.assertEqual({player.pk for player in matching}, {player.pk for player in known})

    def test_exact_thresholds_do_not_match_strict_comparisons(self):
        conditions = self.stat_conditions(self.make_players(career_stats=worlds_stats(games=10, wins=5)))
        triples = {(c[2], c[3], c[4]) for c in conditions}
        self.assertNotIn(('worlds_win_rate', 'gt', 50), triples)
        self.assertNotIn(('worlds_win_rate', 'lt', 50), triples)
        self.assertNotIn(('worlds_games', 'gt', 10), triples)
        self.assertNotIn(('worlds_games', 'lt', 10), triples)

    def test_dynamic_choices_do_not_mutate_static_pool(self):
        baseline = list(generator.CONDITION_POOL)
        self.assertTrue(self.stat_conditions(self.make_players()))
        self.assertEqual(generator.CONDITION_POOL, baseline)

    def test_non_worlds_records_cannot_enter_role_pool_or_fallback(self):
        for role in generator.ROLE_ORDER:
            self.make_players(role=role, count=8, attributes={'worlds_verified': False})
        self.assertEqual(generator._role_pool('mid'), [])
        self.assertEqual(self.stat_conditions(Player.objects.all()), [])
        with self.assertRaises(ValueError):
            generator.generate_daily(date=date(2026, 2, 1), seed=1)
        self.assertFalse(Daily.objects.exists())

    def test_invalid_or_too_sparse_stats_do_not_activate_conditions(self):
        players = self.make_players(count=generator.MIN_CANDIDATES - 1)
        self.assertEqual(self.stat_conditions(players), [])
        broken = worlds_stats()
        broken['worlds']['losses'] = 999
        players = self.make_players(role='top', career_stats=broken)
        self.assertEqual(self.stat_conditions(players), [])

    def test_runtime_pool_refreshes_when_stats_change(self):
        self.make_players(career_stats={})
        self.assertEqual(self.stat_conditions(Player.objects.all()), [])
        Player.objects.update(career_stats=worlds_stats(champion='New Champion'))
        conditions = self.stat_conditions(Player.objects.all())
        self.assertIn('New Champion', [c[4] for c in conditions if c[2] == 'worlds_top5_champion'])
        Player.objects.update(career_stats=worlds_stats(champion='Another Champion'))
        conditions = self.stat_conditions(Player.objects.all())
        self.assertNotIn('New Champion', [c[4] for c in conditions if c[2] == 'worlds_top5_champion'])

    def test_top_five_includes_ties_without_using_unranked_champions(self):
        stats = worlds_stats(games=26, wins=13)
        stats['worlds']['champions'] = [
            {'champion': name, 'games': games, 'wins': wins}
            for name, games, wins in [('A', 7, 4), ('B', 5, 3), ('C', 4, 2), ('D', 3, 1),
                                     ('E', 3, 1), ('F', 3, 1), ('G', 1, 1)]
        ]
        conditions = self.stat_conditions(self.make_players(career_stats=stats))
        champions = {c[4] for c in conditions if c[2] == 'worlds_top5_champion'}
        self.assertEqual(champions, {'A', 'B', 'C', 'D', 'E', 'F'})

    def test_top_five_is_parsed_once_per_verified_player(self):
        players = self.make_players(count=generator.MIN_CANDIDATES)
        excluded = self.make_players(role='adc', attributes={'worlds_verified': False})
        original = generator.PlayerFacts.worlds_top5_champions.fget
        parsed = []

        def top_five(facts):
            parsed.append(facts.player.pk)
            return original(facts)

        with patch.object(generator.PlayerFacts, 'worlds_top5_champions', new=property(top_five)):
            conditions = self.stat_conditions(players + excluded)
        self.assertIn('Azir', [c[4] for c in conditions if c[2] == 'worlds_top5_champion'])
        self.assertCountEqual(parsed, [player.pk for player in players])

    def test_champion_support_uses_validator_normalization_and_refreshes_at_eight(self):
        players = self.make_players(count=generator.MIN_CANDIDATES)
        for index, player in enumerate(players):
            player.career_stats = worlds_stats(champion="Cho'Gath" if index % 2 else 'Cho’Gath')
        champions = {c[4] for c in self.stat_conditions(players) if c[2] == 'worlds_top5_champion'}
        self.assertEqual(champions, {"Cho'Gath", 'Cho’Gath'})
        players[-1].career_stats = worlds_stats(champion='Lux')
        self.assertEqual([c for c in self.stat_conditions(players) if c[2] == 'worlds_top5_champion'], [])

    def test_no_pair_is_generated_when_neither_clue_narrows_the_pool(self):
        players = self.make_players(count=generator.MIN_CANDIDATES)
        daily = Daily.objects.create(date=date(2026, 1, 1))
        conditions = [
            ('origin', generator.EASY, 'country', 'eq', 'KR', 'Koreańczyk', 'Korean'),
            ('status', generator.EASY, 'active', 'eq', True, 'Aktywny', 'Active'),
        ]
        with self.assertRaisesRegex(ValueError, 'independent requirements'):
            generator.generate_slot(daily, 'mid', 1, generator.HARD,
                                    random.Random(1), set(), players, conditions)
        self.assertFalse(daily.slots.exists())

    def test_generation_parses_each_champion_ranking_once_for_all_champion_clues(self):
        players = self.make_players(count=30)
        for index, player in enumerate(players):
            player.country_code = 'KR' if index < 20 else 'CN'
            player.career_stats = worlds_stats(champion='Lux' if 10 <= index < 20 else 'Azir')
            player.save()
        daily = Daily.objects.create(date=date(2026, 1, 1))
        clues = [
            ('origin', generator.EASY, 'country', 'eq', 'KR', 'Koreańczyk', 'Korean'),
            ('champion', generator.HARD, 'worlds_top5_champion', 'eq', 'Azir', 'Azir', 'Azir'),
            ('champion', generator.HARD, 'worlds_top5_champion', 'eq', 'Lux', 'Lux', 'Lux'),
        ]
        parsed = []
        original = generator.PlayerFacts.worlds_top5_champions.fget

        def top_five(facts):
            parsed.append(facts.player.pk)
            return original(facts)

        with patch.object(generator.PlayerFacts, 'worlds_top5_champions', new=property(top_five)):
            slot, candidates = generator.generate_slot(daily, 'mid', 1, generator.HARD,
                                                       random.Random(1), set(), players, clues)
        self.assertCountEqual(parsed, [p.pk for p in players])
        self.assertEqual({p.pk for p in candidates}, {p.pk for p in generator.count_candidates(slot)})
        self.assertEqual(len(candidates), 10)

    def test_less_than_win_rate_and_games_thresholds(self):
        conditions = self.stat_conditions(self.make_players(career_stats=worlds_stats(games=8, wins=3)))
        triples = {(c[2], c[3], c[4]) for c in conditions}
        self.assertIn(('worlds_win_rate', 'lt', 50), triples)
        self.assertIn(('worlds_games', 'lt', 10), triples)
        self.assertNotIn(('worlds_win_rate', 'gt', 50), triples)

    def test_specific_champion_is_standalone_without_statistical_padding(self):
        players = self.make_players(count=80)
        for index, player in enumerate(players):
            player.career_stats = worlds_stats(games=30 if index < 16 else 110,
                                               champion='Olaf' if index < 20 else 'Azir')
            player.save()
        clues = [
            ('worlds_top5_champion', generator.MEDIUM, 'worlds_top5_champion', 'eq', 'Olaf', 'Olaf', 'Olaf'),
            ('worlds_games', generator.EASY, 'worlds_games', 'lt', 100, '<100', '<100'),
        ]
        daily = Daily.objects.create(date=date(2026, 1, 1))
        slot, candidates = generator.generate_slot(daily, 'mid', 1, generator.MEDIUM,
                                                  random.Random(1), set(), players, clues)
        self.assertEqual(list(slot.conditions.values_list('condition_type', flat=True)), ['worlds_top5_champion'])
        self.assertEqual(len(candidates), 20)

    def test_too_broad_champion_does_not_gain_a_numeric_filler(self):
        players = self.make_players(count=80)
        for index, player in enumerate(players):
            player.career_stats = worlds_stats(games=30 if index < 16 else 110)
            player.save()
        daily = Daily.objects.create(date=date(2026, 1, 1))
        clues = [
            ('worlds_top5_champion', generator.MEDIUM, 'worlds_top5_champion', 'eq', 'Azir', 'Azir', 'Azir'),
            ('worlds_games', generator.EASY, 'worlds_games', 'lt', 100, '<100', '<100'),
        ]
        with self.assertRaisesRegex(ValueError, 'independent requirements'):
            generator.generate_slot(daily, 'mid', 1, generator.MEDIUM, random.Random(1), set(), players, clues)

    def test_recent_themes_remembers_dynamic_champion_even_after_data_disappears(self):
        daily = Daily.objects.create(date=date(2026, 1, 1))
        slot = DailySlot.objects.create(daily=daily, role='mid', position=1)
        DailySlotCondition.objects.create(slot=slot, condition_type='worlds_top5_champion',
                                          operator='eq', value='Removed Champion')
        self.assertIn(generator.STAT_THEMES['worlds_top5_champion'],
                      generator.recent_themes(date(2026, 1, 2)))
        DailySlotCondition.objects.create(slot=slot, condition_type='worlds_top5_champion',
                                          operator='eq', value='Another Champion')
        self.assertEqual(generator.recent_themes(date(2026, 1, 2))['worlds_top5_champion'], 2)

    def test_generated_rosters_can_use_every_new_type_and_remain_solvable(self):
        for role in generator.ROLE_ORDER:
            players = self.make_players(role=role, count=64)
            for index, player in enumerate(players):
                games = (8, 30, 60, 110)[(index // 4) % 4]
                player.country_code = 'KR' if index % 2 else 'CN'
                player.is_active = bool(index & 2)
                player.career_stats = worlds_stats(games=games, wins=int(games * (0.7 if index & 16 else 0.3)),
                                                   champion='Lux' if index & 32 else 'Azir')
            Player.objects.bulk_update(players, ['country_code', 'is_active', 'career_stats'])
        seen = set()
        for offset in range(20):
            daily = generator.generate_daily(date=date(2026, 2, 1) + timedelta(days=offset), seed=offset)
            slots = list(daily.slots.prefetch_related('conditions'))
            pools = [generator.count_candidates(slot) for slot in slots]
            self.assertEqual([slot.role for slot in slots], generator.ROLE_ORDER)
            self.assertTrue(all(generator.MIN_CANDIDATES <= len(pool) <= generator.MAX_CANDIDATES for pool in pools))
            self.assertTrue(generator._has_distinct_roster(pools))
            self.assertTrue(all(len(slot.conditions.all()) == 2 for slot in slots))
            theme_map = {c[2]: c[0] for c in generator.CONDITION_POOL}
            theme_map.update(generator.STAT_THEMES)
            for slot in slots:
                self.assertEqual(len({theme_map[c.condition_type] for c in slot.conditions.all()}), 2)
            seen.update(condition.condition_type for slot in slots for condition in slot.conditions.all())
        self.assertTrue({kind for kind in generator.STAT_THEMES if kind.startswith('worlds_')} <= seen)
