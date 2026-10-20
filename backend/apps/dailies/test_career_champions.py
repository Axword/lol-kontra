from copy import deepcopy
from types import SimpleNamespace

from unittest import TestCase

from .generator import MIN_CANDIDATES, build_condition_pool
from .validators import PlayerFacts, evaluate_condition


def stats(champion='Azir'):
    return {'games': 20, 'wins': 12, 'losses': 8,
            'champions': [{'champion': champion, 'games': 20, 'wins': 12}],
            'source': 'Leaguepedia', 'scope': 'leaguepedia_career', 'complete': True}


def player(career=None):
    return SimpleNamespace(attributes={'worlds_verified': True}, career_stats={'career': career or stats()})


class CareerChampionTests(TestCase):
    def test_career_and_worlds_are_independent_and_accept_any_exact_champion(self):
        p = player(stats('Hwei'))
        p.career_stats['worlds'] = {**stats('Azir'), 'scope': 'worlds_including_play_in'}
        self.assertTrue(evaluate_condition(p, 'career_top5_champion', 'eq', 'Hwei'))
        self.assertFalse(evaluate_condition(p, 'worlds_top5_champion', 'eq', 'Hwei'))
        self.assertTrue(evaluate_condition(p, 'worlds_top5_champion', 'eq', 'Azir'))
        self.assertFalse(evaluate_condition(p, 'career_top5_champion', 'eq', 'Azir'))
        self.assertFalse(evaluate_condition(p, 'career_top5_champion', 'eq', 'Hwe'))

    def test_ties_at_fifth_are_included_but_sixth_lower_rank_is_not(self):
        data = stats()
        data['champions'] = [{'champion': name, 'games': count, 'wins': 0}
                             for name, count in [('Ahri', 7), ('Azir', 5), ('Zed', 4), ('Ryze', 3), ('Lux', 3), ('Orianna', 3), ('Annie', 1)]]
        data.update(games=26, wins=0, losses=26)
        p = player(data)
        self.assertEqual(len(PlayerFacts(p).career_top5_champions), 6)
        self.assertTrue(evaluate_condition(p, 'career_top5_champion', 'eq', 'Orianna'))
        self.assertFalse(evaluate_condition(p, 'career_top5_champion', 'eq', 'Annie'))

    def test_unknown_incomplete_wrong_scope_and_favorites_never_substitute(self):
        for changed in ({'complete': False}, {'scope': 'worlds_including_play_in'}, {'source': 'Favorites'},
                        {'champions': []}, {'wins': 999}, {'games': True}):
            p = player({**stats(), **changed})
            p.attributes['favorite_champions'] = ['Azir']
            p.attributes['top_champions_career'] = ['Azir']
            with self.subTest(changed=changed):
                self.assertFalse(evaluate_condition(p, 'career_top5_champion', 'eq', 'Azir'))
        p = player()
        p.career_stats = {}
        self.assertFalse(evaluate_condition(p, 'career_top5_champion', 'eq', 'Azir'))

    def test_only_eq_and_full_consistent_breakdown_are_allowed(self):
        p = player(stats("Cho'Gath"))
        self.assertTrue(evaluate_condition(p, 'career_top5_champion', 'eq', 'Cho’Gath'))
        for operator in ('in', 'gt', 'any', 'typo'):
            self.assertFalse(evaluate_condition(p, 'career_top5_champion', operator, "Cho'Gath"))
        p.career_stats['career']['champions'].append(deepcopy(p.career_stats['career']['champions'][0]))
        self.assertFalse(evaluate_condition(p, 'career_top5_champion', 'eq', "Cho'Gath"))

    def test_generator_refreshes_career_choices_and_honors_eight_player_support(self):
        players = [player(stats('Hwei')) for _ in range(MIN_CANDIDATES)]
        career = lambda: [c for c in build_condition_pool(players) if c[2] == 'career_top5_champion']
        self.assertEqual([c[4] for c in career()], ['Hwei'])
        self.assertEqual(career()[0][5], 'Hwei w jego TOP 5 według liczby gier w karierze')
        players[-1].attributes['worlds_verified'] = False
        self.assertEqual(career(), [])
        for p in players:
            p.attributes['worlds_verified'] = True
            p.career_stats = {'career': stats('Annie')}
        self.assertEqual([c[4] for c in career()], ['Annie'])
