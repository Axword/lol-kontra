from types import SimpleNamespace
from unittest import TestCase

from .models import valid_requirement_count
from .validators import evaluate_condition


def player(history=None, **attributes):
    return SimpleNamespace(attributes={
        'worlds_verified': True,
        'worlds_team_years': {'Invictus Gaming': [2018, 2019]} if history is None else history,
        **attributes,
    })


class WorldsTeamYearTests(TestCase):
    def matches(self, subject, value, operator='eq'):
        return evaluate_condition(subject, 'worlds_team_year', operator, value)

    def test_before_is_exclusive_and_exact_year_is_independent(self):
        for year, expected in [(2025, True), (2026, False), (2027, False)]:
            with self.subTest(year=year):
                self.assertEqual(self.matches(player({'IG': [year]}), {'team': 'ig', 'before': 2026}), expected)
        self.assertTrue(self.matches(player(), {'team': 'invictus-gaming', 'year': 2018}))
        self.assertFalse(self.matches(player(), {'team': 'ig', 'year': 2020}))

    def test_normalizes_team_aliases_and_combines_matching_history_entries(self):
        self.assertTrue(self.matches(player({'Invictus Gaming': [2026], 'IG': [2015]}),
                                     {'team': 'invictus-gaming', 'before': 2020}))
        self.assertTrue(self.matches(player({'TOP Esports': [2020]}), {'team': 'tes', 'year': 2020}))
        self.assertFalse(self.matches(player(), {'team': 'tes', 'before': 2026}))

    def test_career_membership_and_missing_or_unverified_history_never_substitute(self):
        for history in ({}, [], 'IG', {'Fnatic': [2018]}):
            self.assertFalse(self.matches(player(history, team_years={'IG': [2018]}, teams=['IG']),
                                          {'team': 'ig', 'before': 2026}))
        for verification in (False, None, 'true', 1):
            self.assertFalse(self.matches(player(worlds_verified=verification), {'team': 'ig', 'year': 2018}))
        subject = player()
        del subject.attributes['worlds_verified']
        self.assertFalse(self.matches(subject, {'team': 'ig', 'year': 2018}))

    def test_malformed_values_and_history_fail_closed(self):
        values = [None, [], 'IG', {}, {'team': 'IG'}, {'team': None, 'year': 2018},
                  {'team': '', 'before': 2026}, {'team': 'IG', 'year': True},
                  {'team': 'IG', 'year': '2018'}, {'team': 'IG', 'before': '2026'},
                  {'team': 'IG', 'year': 2010}, {'team': 'IG', 'before': 2102},
                  {'team': 'IG', 'year': 2018, 'before': 2026},
                  {'team': 'IG', 'year': 2018, 'extra': True}]
        for value in values:
            with self.subTest(value=value):
                self.assertFalse(self.matches(player(), value))
        for entries in (None, 2018, '2018', [], [True], ['2018'], [2018, None], [2010], [2101]):
            with self.subTest(entries=entries):
                self.assertFalse(self.matches(player({'IG': entries}), {'team': 'ig', 'before': 2026}))

    def test_only_eq_and_single_narrow_requirement_are_allowed(self):
        for operator in ('in', 'gte', 'lte', 'gt', 'lt', 'any', 'unknown'):
            self.assertFalse(self.matches(player(), {'team': 'ig', 'year': 2018}, operator))
        self.assertTrue(valid_requirement_count([SimpleNamespace(condition_type='worlds_team_year')]))


class BirthCountryTests(TestCase):
    def test_birthplace_is_independent_of_current_nationality(self):
        subject = player(leaguepedia_country_of_birth='China')
        subject.country_code = 'CA'
        self.assertTrue(evaluate_condition(subject, 'birth_country', 'eq', 'CN'))
        self.assertTrue(evaluate_condition(subject, 'country', 'eq', 'CA'))
        self.assertFalse(evaluate_condition(subject, 'birth_country', 'eq', 'CA'))

    def test_missing_unknown_or_malformed_birthplace_never_uses_nationality(self):
        subject = player()
        subject.country_code = 'CN'
        for value in (None, '', 'Unknown', True, ['China']):
            with self.subTest(value=value):
                subject.attributes['leaguepedia_country_of_birth'] = value
                self.assertFalse(evaluate_condition(subject, 'birth_country', 'eq', 'CN'))
                self.assertFalse(evaluate_condition(subject, 'birth_country', 'any', None))
        del subject.attributes['leaguepedia_country_of_birth']
        self.assertFalse(evaluate_condition(subject, 'birth_country', 'eq', 'CN'))

    def test_source_names_codes_aliases_case_and_supported_operators(self):
        for source in ('China', 'CHINA', ' cn '):
            self.assertTrue(evaluate_condition(player(leaguepedia_country_of_birth=source),
                                               'birth_country', 'eq', 'CN'))
        subject = player(leaguepedia_country_of_birth=' Republic of Korea ')
        self.assertTrue(evaluate_condition(subject, 'birth_country', 'in', ['CN', 'KR']))
        self.assertTrue(evaluate_condition(subject, 'birth_country', 'any', None))
        self.assertFalse(evaluate_condition(subject, 'birth_country', 'gte', 'KR'))
        self.assertTrue(valid_requirement_count([SimpleNamespace(condition_type='birth_country')]))
