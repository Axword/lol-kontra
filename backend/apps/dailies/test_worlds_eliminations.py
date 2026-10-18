from types import SimpleNamespace
from unittest import TestCase

from .generator import CONDITION_POOL, HARD, MEDIUM, _candidates_for_conditions, _independent_conditions
from .validators import evaluate_condition


def player(history=None):
    return SimpleNamespace(pk=1, primary_role='mid', secondary_roles=[],
                           attributes={'worlds_verified': True, 'worlds_eliminations': history})


class WorldsEliminationConditionTests(TestCase):
    def test_positive_known_seasons_survive_partial_history_and_other_years_titles(self):
        p = player({'quarterfinal': [2014], 'semifinal': [2016], 'final': [2018]})
        p.attributes.update(worlds_eliminations_meta={'complete': False}, worlds_titles=[2017])
        for stage in ('quarterfinal', 'semifinal', 'final'):
            self.assertTrue(evaluate_condition(p, 'worlds_eliminated_stage', 'eq', stage))
        self.assertFalse(evaluate_condition(p, 'worlds_eliminated_stage', 'eq', 'play_in'))

    def test_unknown_or_empty_history_never_proves_elimination(self):
        for history in (None, {}, [], {'group': []}, {'group': None}, {'group': False}, {'group': [False, 0, 'unknown']}):
            with self.subTest(history=history):
                self.assertFalse(evaluate_condition(player(history), 'worlds_eliminated_stage', 'eq', 'group'))

    def test_only_explicit_stage_eq_is_supported_and_false_is_never_a_negative_claim(self):
        p = player({'group': [2023]})
        for stage in ('unknown', 'swiss', '', False, True, 0, {'stage': 'group'}, ['group']):
            with self.subTest(stage=stage):
                self.assertFalse(evaluate_condition(p, 'worlds_eliminated_stage', 'eq', stage))
        for operator in ('neq', 'ne', 'in', 'any', 'gte', 'lt'):
            self.assertFalse(evaluate_condition(p, 'worlds_eliminated_stage', operator, 'group'))

    def test_all_five_stages_have_a_separate_theme_and_meaningful_difficulty(self):
        conditions = [c for c in CONDITION_POOL if c[2] == 'worlds_eliminated_stage']
        self.assertEqual({c[4] for c in conditions}, {'play_in', 'group', 'quarterfinal', 'semifinal', 'final'})
        self.assertTrue(all(c[0] == 'elimination_stage' and c[1] in (MEDIUM, HARD) for c in conditions))
        self.assertNotEqual(conditions[0][0], next(c[0] for c in CONDITION_POOL if c[2] == 'worlds_semifinal'))

    def test_matching_stays_specific_to_the_stage_and_rejects_ineligible_players(self):
        conditions = [c for c in CONDITION_POOL if c[2] == 'worlds_eliminated_stage']
        p = player({'quarterfinal': [2023]})
        quarter = next(c for c in conditions if c[4] == 'quarterfinal')
        final = next(c for c in conditions if c[4] == 'final')
        self.assertEqual(_candidates_for_conditions('mid', [quarter], [p]), [p])
        self.assertEqual(_candidates_for_conditions('mid', [final], [p]), [])
        p.attributes['worlds_verified'] = False
        self.assertEqual(_candidates_for_conditions('mid', [quarter], [p]), [])

    def test_elimination_is_not_paired_with_a_second_description_of_the_same_result(self):
        stage = next(c for c in CONDITION_POOL if c[2] == 'worlds_eliminated_stage' and c[4] == 'final')
        lost_final = next(c for c in CONDITION_POOL if c[2] == 'worlds_final_lost')
        country = next(c for c in CONDITION_POOL if c[2] == 'country')
        self.assertFalse(_independent_conditions(stage, lost_final))
        self.assertFalse(_independent_conditions(lost_final, stage))
        self.assertTrue(_independent_conditions(stage, country))
        self.assertTrue(_independent_conditions(stage, (*lost_final[:4], 2015, *lost_final[5:])))
