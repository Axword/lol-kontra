from datetime import date, timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.players.models import Player
from .generator import MAX_CANDIDATES, MIN_CANDIDATES, ROLE_ORDER, _has_distinct_roster, count_candidates, generate_daily, validate_daily
from .models import Daily, DailySlot, DailySlotCondition
from .tests_validators import FakePlayer
from .validators import evaluate_condition


class EvaluatorRegressionTests(TestCase):
    def test_unknown_or_incompatible_operator_is_rejected(self):
        player = FakePlayer(country_code='KR', worlds_count=5)
        self.assertFalse(evaluate_condition(player, 'country', 'gte', 'KR'))
        self.assertFalse(evaluate_condition(player, 'worlds_count_min', 'typo', 1))

    def test_numeric_appearance_value_is_a_year(self):
        player = FakePlayer(attributes={'worlds_appearances': [2019, 2021]})
        self.assertTrue(evaluate_condition(player, 'worlds_appearance', 'eq', 2019))
        self.assertFalse(evaluate_condition(player, 'worlds_appearance', 'eq', 2020))

    def test_boolean_false_does_not_match_a_finalist(self):
        player = FakePlayer(attributes={'worlds_finals': [2019]})
        self.assertFalse(evaluate_condition(player, 'worlds_final', 'eq', False))

    def test_missing_achievement_data_does_not_prove_negative_claim(self):
        player = FakePlayer(worlds_count=8)
        self.assertFalse(evaluate_condition(player, 'worlds_never_escaped', 'gte', 2))
        self.assertFalse(evaluate_condition(player, 'worlds_never_won', 'gte', 3))
        self.assertFalse(evaluate_condition(player, 'worlds_champion', 'eq', False))

    def test_career_teams_do_not_prove_worlds_organizations(self):
        player = FakePlayer(attributes={'teams': ['t1', 'fnatic', 'g2']})
        self.assertFalse(evaluate_condition(player, 'worlds_teams_min', 'gte', 3))

    def test_career_roles_do_not_prove_worlds_roles(self):
        player = FakePlayer(secondary_roles=['adc'])
        self.assertFalse(evaluate_condition(player, 'worlds_multi_role', 'gte', 2))

    def test_role_in_and_any_operators(self):
        player = FakePlayer(primary_role='mid', secondary_roles=['adc'])
        self.assertTrue(evaluate_condition(player, 'role', 'in', ['top', 'bot']))
        self.assertTrue(evaluate_condition(player, 'role', 'any', None))

    def test_unknown_activity_is_neither_active_nor_retired(self):
        player = FakePlayer(attributes={'activity_verified': False})
        self.assertFalse(evaluate_condition(player, 'active', 'eq', True))
        self.assertFalse(evaluate_condition(player, 'active', 'eq', False))

    def test_history_covers_old_league_names_and_past_imports(self):
        player = FakePlayer(country_code='DK', continent='Europe', residency='LEC',
                            attributes={'leagues': ['EU LCS', 'LEC', 'NA LCS']})
        self.assertTrue(evaluate_condition(player, 'import_player', 'eq', True))
        self.assertTrue(evaluate_condition(player, 'league', 'eq', 'LCS'))
        self.assertTrue(evaluate_condition(player, 'leagues_min', 'gte', 2))
        self.assertFalse(evaluate_condition(player, 'leagues_min', 'gte', 3))

    def test_numeric_operators_and_event_dates(self):
        player = FakePlayer(attributes={'worlds_appearances': [2018, 2020],
                                        'worlds_finals': [2020], 'msi_appearances': [2019]})
        self.assertTrue(evaluate_condition(player, 'worlds_count_min', 'lte', 2))
        self.assertFalse(evaluate_condition(player, 'worlds_count_min', 'lte', 1))
        self.assertTrue(evaluate_condition(player, 'worlds_debut_year', 'in', [2018, 2019]))
        self.assertFalse(evaluate_condition(player, 'worlds_final', 'eq', {'year': 2019}))
        self.assertTrue(evaluate_condition(player, 'msi_appearance', 'eq', 2019))
        self.assertFalse(evaluate_condition(player, 'msi_appearance', 'eq', 2020))


class GeneratorRegressionTests(TestCase):
    def make_pool(self, count=1):
        for role in ROLE_ORDER:
            for index in range(count):
                Player.objects.create(
                    slug=f'{role}-{index}', nickname=f'{role}-{index}', primary_role=role,
                    country_code='TH', residency='PCS', continent='Asia', is_active=False,
                )

    def test_sparse_dataset_is_rejected_instead_of_creating_trivial_slots(self):
        self.make_pool()
        for seed in range(8):
            with self.assertRaises(ValueError):
                generate_daily(date=date(2026, 1, 1) + timedelta(days=seed), seed=seed)
            self.assertFalse(Daily.objects.exists())

    def test_failure_to_find_two_independent_requirements_rolls_back_daily(self):
        self.make_pool(count=8)
        one_condition = [('status', 'easy', 'active', 'eq', False, 'Retired', 'Retired')]
        with patch('apps.dailies.generator.CONDITION_POOL', one_condition), self.assertRaises(ValueError):
            generate_daily(date=date(2026, 1, 1))
        self.assertFalse(Daily.objects.exists())

    def test_existing_single_requirement_board_is_not_treated_as_complete(self):
        self.make_pool(count=8)
        daily = Daily.objects.create(date=date(2026, 1, 1))
        for index, role in enumerate(ROLE_ORDER, 1):
            slot = DailySlot.objects.create(daily=daily, position=index, role=role)
            DailySlotCondition.objects.create(slot=slot, condition_type='active', operator='eq', value=False)
        with self.assertRaises(ValueError):
            generate_daily(date=daily.date)
        self.assertEqual(daily.slots.count(), 5)

    def test_validate_daily_accepts_two_requirements_without_mutating_board(self):
        self.make_pool(count=8)
        daily = generate_daily(date=date(2026, 1, 1))
        before = list(daily.slots.values_list('id', flat=True))
        self.assertEqual(validate_daily(daily), daily)
        self.assertEqual(generate_daily(date=daily.date), daily)
        self.assertEqual(list(daily.slots.values_list('id', flat=True)), before)

    def test_validate_daily_rejects_three_requirements_and_same_theme(self):
        self.make_pool(count=8)
        daily = generate_daily(date=date(2026, 1, 1))
        slot = daily.slots.first()
        extra = DailySlotCondition.objects.create(slot=slot, condition_type='active', operator='eq', value=False)
        with self.assertRaises(ValueError):
            validate_daily(daily)
        extra.delete()
        slot.conditions.update(condition_type='active', operator='eq', value=False)
        with self.assertRaises(ValueError):
            validate_daily(daily)

    def test_validate_daily_rejects_trivial_role_requirements_and_too_few_candidates(self):
        self.make_pool(count=8)
        daily = generate_daily(date=date(2026, 1, 1))
        slot = daily.slots.first()
        Player.objects.filter(primary_role=slot.role).first().delete()
        with self.assertRaises(ValueError):
            validate_daily(daily)
        slot.conditions.filter(condition_type='active').update(condition_type='role', value=slot.role)
        with self.assertRaisesRegex(ValueError, 'two independent requirements'):
            validate_daily(daily)

    def test_generation_failure_does_not_leave_partial_daily(self):
        Player.objects.create(slug='mid', nickname='Mid', primary_role='mid')
        with self.assertRaises(ValueError):
            generate_daily(date=date(2026, 1, 1))
        self.assertFalse(Daily.objects.exists())

    def test_existing_partial_board_is_not_treated_as_complete(self):
        self.make_pool()
        daily = Daily.objects.create(date=date(2026, 1, 1))
        DailySlot.objects.create(daily=daily, position=1, role='top')
        with self.assertRaises(ValueError):
            generate_daily(date=daily.date)

    def test_force_regeneration_cannot_remove_existing_game(self):
        from apps.submissions.models import Submission
        self.make_pool(count=8)
        daily = generate_daily(date=date(2026, 1, 1))
        slots_before = list(daily.slots.values_list('id', flat=True))
        Submission.objects.create(daily=daily, guest_token='keep-me')
        with self.assertRaises(ValueError):
            generate_daily(date=daily.date, force=True)
        self.assertEqual(list(daily.slots.values_list('id', flat=True)), slots_before)

    def test_one_multirole_player_cannot_solve_entire_roster(self):
        Player.objects.create(slug='solo', nickname='Solo', primary_role='mid', secondary_roles=ROLE_ORDER)
        with self.assertRaises(ValueError):
            generate_daily(date=date(2026, 1, 1))
        self.assertFalse(Daily.objects.exists())

    def test_candidate_scan_reuses_prefetched_conditions(self):
        self.make_pool(count=8)
        daily = Daily.objects.create(date=date(2026, 1, 1))
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        DailySlotCondition.objects.create(slot=slot, condition_type='active', operator='eq', value=False)
        with self.assertNumQueries(2):
            self.assertEqual(len(count_candidates(slot)), 8)

    def test_history_simulation_never_labels_invalid_answers_correct(self):
        from .management.commands.seed_history import Command
        self.make_pool(count=8)
        daily = generate_daily(date=date(2026, 1, 1))
        Command().simulate_submissions(daily, 4)
        for submission in daily.submissions.all():
            answers = list(submission.answers.select_related('player', 'daily_slot'))
            self.assertEqual(len({answer.player_id for answer in answers}), 5)
            self.assertEqual(len(answers), 5)
            for answer in answers:
                self.assertIn(answer.player, count_candidates(answer.daily_slot))

    def test_history_simulation_rejects_unanswerable_conditions(self):
        from .management.commands.seed_history import Command
        self.make_pool(count=8)
        daily = generate_daily(date=date(2026, 1, 1))
        slot = daily.slots.first()
        slot.conditions.update(condition_type='country', operator='eq', value='ZZ')
        with self.assertRaises(ValueError):
            Command().simulate_submissions(daily, 1)
        self.assertFalse(daily.submissions.exists())


class CanonicalGenerationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        import io
        call_command('seed_players', full=True, stdout=io.StringIO())

    def test_thirty_days_have_playable_distinct_rosters(self):
        seen = set()
        for index in range(30):
            with self.subTest(day=index):
                daily = generate_daily(date=date(2026, 1, 1) + timedelta(days=index), seed=index)
                slots = list(daily.slots.prefetch_related('conditions'))
                self.assertEqual([slot.role for slot in slots], ROLE_ORDER)
                pools = [count_candidates(slot) for slot in slots]
                self.assertTrue(all(len(slot.conditions.all()) == 2 for slot in slots))
                self.assertTrue(all(MIN_CANDIDATES <= len(pool) <= MAX_CANDIDATES for pool in pools))
                self.assertTrue(_has_distinct_roster(pools))
                seen.update(condition.condition_type for slot in slots for condition in slot.conditions.all())
        self.assertTrue({'worlds_win_rate', 'worlds_games', 'worlds_top5_champion'} <= seen)


@override_settings(REST_FRAMEWORK={'DEFAULT_THROTTLE_CLASSES': []})
class DailyVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        today = timezone.localdate()
        self.published = Daily.objects.create(date=today - timedelta(days=1), status='published')
        self.draft = Daily.objects.create(date=today, status='draft')
        self.future = Daily.objects.create(date=today + timedelta(days=1), status='published')

    def test_list_hides_draft_and_future_dailies(self):
        response = self.client.get('/api/v1/dailies/')
        self.assertEqual(response.status_code, 200)
        data = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        self.assertEqual([item['id'] for item in data], [self.published.id])

    def test_retrieve_and_slots_hide_draft_and_future_dailies(self):
        for daily in (self.draft, self.future):
            for suffix in ('', 'slots/'):
                with self.subTest(daily=daily.id, suffix=suffix):
                    self.assertEqual(self.client.get(f'/api/v1/dailies/{daily.id}/{suffix}').status_code, 404)

    def test_today_does_not_publish_or_reveal_draft(self):
        self.assertEqual(self.client.get('/api/v1/dailies/today/').status_code, 404)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, 'draft')
        self.assertFalse(self.draft.slots.exists())

    def test_missing_today_with_empty_players_returns_unavailable(self):
        self.draft.delete()
        self.assertEqual(self.client.get('/api/v1/dailies/today/').status_code, 503)
        self.assertFalse(Daily.objects.filter(date=timezone.localdate()).exists())
