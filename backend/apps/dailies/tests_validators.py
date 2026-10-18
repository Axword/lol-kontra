"""
Testy evaluatora warunków. Nie wymagają bazy – działają na atrapach zawodnika i slotu,
dzięki czemu chodzą w CI bez PostgreSQL.

    python -m unittest apps.dailies.tests_validators
"""
import unittest

from .validators import evaluate_condition, player_matches_slot


class FakePlayer:
    def __init__(self, **kw):
        self.nickname = kw.get('nickname', 'Test')
        self.slug = kw.get('slug', 'test')
        self.country_code = kw.get('country_code', 'KR')
        self.continent = kw.get('continent', 'Asia')
        self.residency = kw.get('residency', 'LCK')
        self.primary_role = kw.get('primary_role', 'mid')
        self.secondary_roles = kw.get('secondary_roles', [])
        self.is_active = kw.get('is_active', True)
        self.birth_year = kw.get('birth_year', 1996)
        self.attributes = kw.get('attributes', {})
        self.worlds_count = kw.get('worlds_count', 0)
        self.worlds_titles_count = kw.get('worlds_titles_count', 0)


class FakeCondition:
    def __init__(self, condition_type, operator, value):
        self.condition_type = condition_type
        self.operator = operator
        self.value = value


class FakeSlot:
    def __init__(self, role, conditions):
        self.role = role
        self.conditions = type('M', (), {'all': lambda s: conditions})()


FAKER = FakePlayer(
    nickname='Faker', primary_role='mid', country_code='KR', residency='LCK',
    worlds_count=8, worlds_titles_count=5,
    attributes={
        'worlds_appearances': [2013, 2015, 2016, 2017, 2019, 2021, 2022, 2023],
        'worlds_titles': [2013, 2015, 2016, 2023],
        'worlds_finals': [2013, 2015, 2016, 2017, 2022, 2023],
        'teams': ['SK Telecom T1', 'T1'], 'worlds_teams': ['t1'],
        'leagues': ['LCK'], 'worlds_roles': ['mid'], 'msi_appearances': [2016, 2017],
    },
)

CAPS = FakePlayer(
    nickname='Caps', primary_role='mid', country_code='DK', continent='Europe',
    residency='LEC', worlds_count=7,
    attributes={
        'worlds_appearances': [2017, 2018, 2019, 2020, 2021, 2022, 2023],
        'worlds_titles': [],
        'worlds_finals': [2018], 'teams': ['Fnatic', 'G2'],
        'worlds_teams': ['fnatic', 'g2'], 'leagues': ['LEC'], 'worlds_roles': ['mid'],
    },
)

PERKZ = FakePlayer(
    nickname='Perkz', primary_role='mid', secondary_roles=['adc'], country_code='HR',
    continent='Europe', residency='LCS',
    attributes={
        'worlds_roles': ['mid', 'adc'], 'leagues': ['LEC', 'LCS'],
        'worlds_appearances': [2016, 2017, 2018, 2019, 2021],
    },
)

KERIA = FakePlayer(nickname='Keria', primary_role='support', residency='LCK', country_code='KR')


class RoleEnforcementTests(unittest.TestCase):
    """Regresja: rola slotu była wcześniej ignorowana."""

    def test_support_nie_pasuje_do_slotu_mid(self):
        slot = FakeSlot('mid', [FakeCondition('country', 'eq', 'KR')])
        self.assertFalse(player_matches_slot(KERIA, slot))

    def test_mid_pasuje_do_slotu_mid(self):
        slot = FakeSlot('mid', [FakeCondition('country', 'eq', 'KR')])
        self.assertTrue(player_matches_slot(FAKER, slot))

    def test_rola_dodatkowa_sie_liczy(self):
        slot = FakeSlot('adc', [FakeCondition('continent', 'eq', 'Europe')])
        self.assertTrue(player_matches_slot(PERKZ, slot))


class StrictnessTests(unittest.TestCase):
    """Regresja: brak danych i nieznane warunki przepuszczały każdego."""

    def test_nieznany_warunek_nie_przepuszcza(self):
        self.assertFalse(evaluate_condition(FAKER, 'wymyslony_warunek', 'eq', 1))

    def test_brak_danych_o_pentakillach(self):
        self.assertFalse(evaluate_condition(FAKER, 'pentakill_worlds', 'gte', 1))

    def test_brak_danych_o_championach(self):
        self.assertFalse(evaluate_condition(FAKER, 'champion_played', 'eq', 'ryze'))


class ConditionTests(unittest.TestCase):
    def test_worlds_champion(self):
        self.assertTrue(evaluate_condition(FAKER, 'worlds_champion', 'eq', True))
        self.assertFalse(evaluate_condition(CAPS, 'worlds_champion', 'eq', True))

    def test_przegrany_final(self):
        self.assertTrue(evaluate_condition(CAPS, 'worlds_final_lost', 'eq', True))
        self.assertTrue(evaluate_condition(FAKER, 'worlds_final_lost', 'eq', True))

    def test_liczba_organizacji_na_worlds(self):
        self.assertTrue(evaluate_condition(CAPS, 'worlds_teams_min', 'gte', 2))
        self.assertFalse(evaluate_condition(FAKER, 'worlds_teams_min', 'gte', 2))

    def test_dwie_role_i_dwie_ligi(self):
        self.assertTrue(evaluate_condition(PERKZ, 'worlds_multi_role', 'gte', 2))
        self.assertTrue(evaluate_condition(PERKZ, 'leagues_min', 'gte', 2))

    def test_import(self):
        self.assertTrue(evaluate_condition(PERKZ, 'import_player', 'eq', True))
        self.assertFalse(evaluate_condition(FAKER, 'import_player', 'eq', True))

    def test_era_s1_s3(self):
        self.assertTrue(evaluate_condition(FAKER, 'worlds_early_era', 'eq', True))
        self.assertFalse(evaluate_condition(CAPS, 'worlds_early_era', 'eq', True))

    def test_debiut_i_liczba_startow(self):
        self.assertTrue(evaluate_condition(FAKER, 'worlds_debut_year', 'lte', 2015))
        self.assertTrue(evaluate_condition(FAKER, 'worlds_count_min', 'gte', 6))

    def test_nigdy_nie_wygral(self):
        self.assertTrue(evaluate_condition(CAPS, 'worlds_never_won', 'gte', 3))
        self.assertFalse(evaluate_condition(FAKER, 'worlds_never_won', 'gte', 3))

    def test_aliasy_druzyn(self):
        self.assertTrue(evaluate_condition(FAKER, 'team', 'eq', 't1'))
        self.assertTrue(evaluate_condition(CAPS, 'team', 'eq', 'g2'))

    def test_liga(self):
        self.assertTrue(evaluate_condition(CAPS, 'residency', 'eq', 'LEC'))
        self.assertFalse(evaluate_condition(CAPS, 'residency', 'eq', 'LCK'))

    def test_rok_urodzenia(self):
        self.assertTrue(
            evaluate_condition(FAKER, 'birth_year_range', 'eq', {'min': 1990, 'max': 1999})
        )


class SlotTests(unittest.TestCase):
    def test_wszystkie_warunki_musza_byc_spelnione(self):
        slot = FakeSlot('mid', [
            FakeCondition('residency', 'eq', 'LCK'),
            FakeCondition('worlds_champion', 'eq', True),
        ])
        self.assertTrue(player_matches_slot(FAKER, slot))
        self.assertFalse(player_matches_slot(CAPS, slot))

    def test_slot_bez_warunkow_nie_przyjmuje_nikogo(self):
        self.assertFalse(player_matches_slot(FAKER, FakeSlot('mid', [])))


if __name__ == '__main__':
    unittest.main()
