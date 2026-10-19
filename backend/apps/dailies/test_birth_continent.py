import importlib
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.players.models import Player
from apps.scoring.models import ScoringConfig
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from .generator import CONDITION_POOL, recent_themes
from .models import Daily, DailySlot, DailySlotCondition
from .validators import evaluate_condition


def person(birth_country=None, **overrides):
    defaults = dict(country_code='US', continent='North America', residency='LCS',
                    primary_role='support', secondary_roles=[],
                    attributes={'leaguepedia_country_of_birth': birth_country, 'worlds_verified': True})
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class BirthContinentConditionTests(SimpleTestCase):
    def test_huhi_and_biofrost_birthplaces_are_distinct_from_nationality(self):
        for player, expected in [(person('France'), 'Europe'), (person('China', country_code='CA'), 'Asia')]:
            self.assertTrue(evaluate_condition(player, 'continent', 'eq', 'North America'))
            self.assertFalse(evaluate_condition(player, 'birth_continent', 'eq', 'North America'))
            self.assertTrue(evaluate_condition(player, 'birth_continent', 'eq', expected))

    def test_native_north_american_matches_both_independent_facts(self):
        player = person('United States')
        self.assertTrue(evaluate_condition(player, 'birth_continent', 'eq', 'North America'))
        self.assertTrue(evaluate_condition(player, 'continent', 'eq', 'North America'))

    def test_unknown_malformed_or_missing_birth_country_never_uses_nationality_or_league(self):
        for value in [None, '', 'unknown', 'Europe', 'LCS', [], ['United States'], {}, {'country': 'US'}, True, 123]:
            with self.subTest(value=value):
                player = person(value)
                player.attributes.update(leaguepedia_nationality_primary='United States', country='US', leagues=['LCS'])
                for operator, target in [('eq', 'North America'), ('in', ['North America']), ('any', None)]:
                    self.assertFalse(evaluate_condition(player, 'birth_continent', operator, target))
                self.assertTrue(evaluate_condition(player, 'continent', 'eq', 'North America'))
        player = person()
        player.attributes.pop('leaguepedia_country_of_birth')
        self.assertFalse(evaluate_condition(player, 'birth_continent', 'any', None))

    def test_explicit_country_aliases_and_codes_are_normalized(self):
        for value, expected in [(' france ', 'Europe'), ('FR', 'Europe'), ('USA', 'North America'),
                                ('United States of America', 'North America'), ('KR', 'Asia')]:
            with self.subTest(value=value):
                self.assertTrue(evaluate_condition(person(value), 'birth_continent', 'eq', expected))

    def test_birth_continent_has_scalar_operators_and_rejects_incompatible_comparisons(self):
        player = person('France')
        self.assertTrue(evaluate_condition(player, 'birth_continent', 'in', ['Europe', 'Asia']))
        self.assertTrue(evaluate_condition(player, 'birth_continent', 'any', None))
        for operator in ['gte', 'lte', 'gt', 'lt', 'ne', 'unknown']:
            self.assertFalse(evaluate_condition(player, 'birth_continent', operator, 'Europe'))
        self.assertFalse(evaluate_condition(player, 'birth_continent', 'in', []))
        self.assertFalse(evaluate_condition(player, 'birth_continent', 'eq', ['Europe']))

    def test_unverified_player_cannot_match_even_a_known_birthplace(self):
        player = person('France')
        player.attributes['worlds_verified'] = False
        self.assertFalse(evaluate_condition(player, 'birth_continent', 'eq', 'Europe'))

    def test_generator_uses_literal_birthplace_labels_in_the_existing_origin_theme(self):
        entries = [entry for entry in CONDITION_POOL if entry[2] == 'birth_continent']
        self.assertEqual({entry[4] for entry in entries}, {'Europe', 'North America'})
        self.assertTrue(all(entry[0] == 'origin' and entry[3] == 'eq' for entry in entries))
        self.assertEqual({entry[4]: entry[5:] for entry in entries}, {
            'Europe': ('Urodzony w Europie', 'Born in Europe'),
            'North America': ('Urodzony w Ameryce Północnej', 'Born in North America'),
        })
        self.assertFalse(any(entry[2] == 'continent' for entry in CONDITION_POOL))


class GeographicLabelMigrationTests(TestCase):
    def setUp(self):
        self.daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='published')
        self.slot = DailySlot.objects.create(daily=self.daily, role='support', position=1)
        self.editor = SimpleNamespace(connection=connection)
        self.migration = importlib.import_module('apps.dailies.migrations.0011_birth_continent')

    def condition(self, value='North America', pl='Z Ameryki Północnej', en='North American', **overrides):
        defaults = dict(slot=self.slot, condition_type='continent', operator='eq', value=value,
                        label_pl=pl, label_en=en)
        defaults.update(overrides)
        return DailySlotCondition.objects.create(**defaults)

    def migrate(self):
        self.migration.clarify_legacy_labels(apps, self.editor)

    def test_only_matching_auto_labels_change_with_custom_translations_preserved(self):
        north = self.condition()
        europe = self.condition('Europe', 'Europejczyk', 'European')
        custom = self.condition(pl='Własny opis', en='Custom description')
        mixed_en = self.condition(en='Keep custom English')
        mixed_pl = self.condition('Europe', 'Zachowaj polski opis', 'European')
        different_operator = self.condition(operator='in')
        different_type = self.condition(condition_type='birth_continent')
        different_value = self.condition(value='Asia')
        protected = [custom, different_operator, different_type, different_value]
        saved = {row.pk: (row.label_pl, row.label_en) for row in protected}
        for _ in range(2):
            self.migrate()
            for row in [north, europe, mixed_en, mixed_pl, *protected]:
                row.refresh_from_db()
            self.assertEqual((north.label_pl, north.label_en),
                             ('Narodowość: kraj w Ameryce Północnej', 'Nationality: North American country'))
            self.assertEqual((europe.label_pl, europe.label_en),
                             ('Narodowość: kraj w Europie', 'Nationality: European country'))
            self.assertEqual((mixed_en.label_pl, mixed_en.label_en),
                             ('Narodowość: kraj w Ameryce Północnej', 'Keep custom English'))
            self.assertEqual((mixed_pl.label_pl, mixed_pl.label_en),
                             ('Zachowaj polski opis', 'Nationality: European country'))
            self.assertEqual({row.pk: (row.label_pl, row.label_en) for row in protected}, saved)

    def test_clarification_preserves_history_and_original_continent_eligibility(self):
        condition = self.condition()
        player = Player.objects.create(slug='birth-huhi', nickname='Huhi', primary_role='support',
                                       country_code='US', continent='North America', residency='LCS',
                                       attributes={'leaguepedia_country_of_birth': 'France'})
        game = Submission.objects.create(daily=self.daily, guest_token='birth-history-guest', total_points=3)
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=self.slot, player=player,
                                                 is_correct=True, rarity_percent=3, points_awarded=-97)
        SubmissionAttempt.objects.create(submission=game, daily_slot=self.slot, player=player, is_correct=True)
        saved_daily = Daily.objects.values().get(pk=self.daily.pk)
        saved_slot = DailySlot.objects.values().get(pk=self.slot.pk)
        saved_game = Submission.objects.values().get(pk=game.pk)
        saved_answer = SubmissionAnswer.objects.values().get(pk=answer.pk)
        saved_attempts = list(game.attempts.values())
        saved_condition = DailySlotCondition.objects.values().get(pk=condition.pk)
        self.migrate()
        condition.refresh_from_db()
        self.assertTrue(evaluate_condition(player, condition.condition_type, condition.operator, condition.value))
        self.assertFalse(evaluate_condition(player, 'birth_continent', 'eq', condition.value))
        actual = DailySlotCondition.objects.values().get(pk=condition.pk)
        self.assertEqual({key: value for key, value in actual.items() if key not in ['label_pl', 'label_en']},
                         {key: value for key, value in saved_condition.items() if key not in ['label_pl', 'label_en']})
        self.assertEqual(Daily.objects.values().get(pk=self.daily.pk), saved_daily)
        self.assertEqual(DailySlot.objects.values().get(pk=self.slot.pk), saved_slot)
        self.assertEqual(Submission.objects.values().get(pk=game.pk), saved_game)
        self.assertEqual(SubmissionAnswer.objects.values().get(pk=answer.pk), saved_answer)
        self.assertEqual(list(game.attempts.values()), saved_attempts)

    def test_legacy_continent_still_counts_as_recent_origin_theme(self):
        self.condition()
        self.assertIn('origin', recent_themes(timezone.localdate()))
        DailySlotCondition.objects.all().delete()
        self.condition('Europe', 'Europejczyk', 'European')
        self.assertIn('origin', recent_themes(timezone.localdate()))

    def test_calendar_replay_does_not_restore_old_ambiguous_labels(self):
        condition = self.condition()
        self.migrate()
        condition.refresh_from_db()
        labels = (condition.label_pl, condition.label_en)
        calendar = importlib.import_module('apps.dailies.migrations._october_2026_release')
        ScoringConfig.objects.create(is_active=True)
        # Existing dates are skipped before their bundled slot labels are read.
        with patch.object(calendar, 'load_calendar', return_value=[{'date': self.daily.date.isoformat(), 'test_rosters': []}]):
            calendar.install_calendar(apps, self.editor)
        condition.refresh_from_db()
        self.assertEqual((condition.label_pl, condition.label_en), labels)
        self.assertEqual(Submission.objects.count(), 0)
