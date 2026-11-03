import random
import sys
import json
from datetime import date
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.test import RequestFactory

from . import board_factory, builder, generator


def clue(kind, value, operator='eq'):
    return ('theme', 'medium', kind, operator, value, kind, kind)


class BoardDiversityTests(SimpleTestCase):
    def test_opponent_questions_cannot_take_over_multiple_positions(self):
        generator.validate_board_diversity([[clue('worlds_opponent_team', 'geng')]])
        with self.assertRaisesRegex(ValueError, 'one opponent requirement'):
            generator.validate_board_diversity([
                [clue('worlds_opponent_team', 'geng')],
                [clue('worlds_beat_player', 'faker')],
            ])

    def test_repeated_origin_cannot_hide_behind_another_country_or_condition_type(self):
        pairs = [
            [clue('birth_country', 'CN'), clue('birth_country', 'CN')],
            [clue('country', 'CN'), clue('country', 'KR')],
            [clue('country', 'CN'), clue('birth_continent', 'Europe')],
            [clue('birth_country', 'CN'), clue('country_excluded', 'KR')],
        ]
        for first, second in pairs:
            with self.subTest(first=first[2:], second=second[2:]), self.assertRaises(ValueError):
                generator.validate_board_diversity([[first], [second]])

    def test_duplicate_requirements_are_detected_without_using_labels_or_aliases(self):
        groups = [
            [clue('league', 'LCS')],
            [{'condition_type': 'residency', 'operator': 'eq', 'value': 'NA LCS', 'label_pl': 'Inne słowa'}],
        ]
        with self.assertRaisesRegex(ValueError, 'same requirement'):
            generator.validate_board_diversity(groups)
        with self.assertRaisesRegex(ValueError, 'same requirement'):
            generator.validate_board_diversity([
                [clue('worlds_games', 25, 'gt')],
                [SimpleNamespace(condition_type='worlds_games', operator='gt', value=25)],
            ])

    def test_two_history_clues_must_refer_to_distinct_normalized_teams(self):
        history = lambda team: clue('worlds_team_year', {'team': team, 'before': 2026})
        generator.validate_board_diversity([[history('invictus-gaming')], [history('top-esports')]])
        with self.assertRaisesRegex(ValueError, 'different teams'):
            generator.validate_board_diversity([[history('Invictus Gaming')], [clue('team', 'IG')]])
        with self.assertRaisesRegex(ValueError, 'at most two'):
            generator.validate_board_diversity([[history('IG')], [history('TES')], [history('Gen.G')]])

    def test_diverse_authored_and_model_conditions_are_accepted_without_mutation(self):
        groups = [
            [clue('worlds_team_year', {'team': 'IG', 'before': 2020})],
            [clue('worlds_team_year', {'team': 'TES', 'before': 2023})],
            [{'condition_type': 'birth_country', 'operator': 'eq', 'value': 'CN'},
             {'condition_type': 'worlds_final', 'operator': 'eq', 'value': True}],
            [SimpleNamespace(condition_type='pentakill_worlds', operator='gte', value=1)],
            [('worlds_title_on_debut', 'eq', True)],
        ]
        before = repr(groups)
        generator.validate_board_diversity(groups)
        self.assertEqual(repr(groups), before)

    def test_slot_generator_does_not_relax_diversity_when_every_option_repeats_origin(self):
        players = [SimpleNamespace(pk=index + 1) for index in range(80)]
        duplicate_origin = clue('birth_country', 'CN')
        with patch.object(generator, '_candidates_for_conditions', return_value=players[:10]), \
                patch.object(generator.DailySlot.objects, 'create') as create:
            with self.assertRaisesRegex(ValueError, 'independent requirements'):
                generator.generate_slot(SimpleNamespace(), 'mid', 1, 'medium', random.Random(2), set(),
                    pool=players, condition_pool=[duplicate_origin],
                    board_conditions=[[clue('country', 'KR')]])
        create.assert_not_called()


class StableRandom:
    def random(self):
        return 1

    def shuffle(self, values):
        pass

    def choice(self, values):
        return values[0]


def option(conditions, role_index, worlds):
    candidates = list(range(role_index * 10 + 1, role_index * 10 + 11))
    return {'conditions': conditions, 'candidate_ids': candidates, 'years': {2019: 10},
            'anchors': ['2019:anchor-team'], 'anchor_players': {'2019:anchor-team': candidates},
            'worlds': worlds}


class FutureFactoryDiversityTests(SimpleTestCase):
    def test_factory_selects_a_different_template_instead_of_a_second_origin(self):
        catalog = {
            'top': [option([clue('birth_country', 'CN'), clue('worlds_final', True)], 0, True)],
            'jungle': [option([clue('birth_country', 'KR'), clue('worlds_games', 25, 'gt')], 1, True),
                       option([clue('worlds_games', 25, 'gt')], 1, True)],
            'mid': [option([clue('pentakill_worlds', 1, 'gte')], 2, True)],
            'adc': [option([clue('team', 'TES')], 3, False)],
            'support': [option([clue('team', 'IG')], 4, False)],
        }
        board, _year = board_factory.choose_board(catalog, StableRandom())
        groups = [entry['conditions'] for entry in board]
        generator.validate_board_diversity(groups)
        self.assertEqual(sum(c[2] in generator.ORIGIN_CONDITIONS for g in groups for c in g), 1)
        self.assertEqual(board[1]['conditions'], [clue('worlds_games', 25, 'gt')])

    def test_factory_fails_instead_of_filling_the_board_with_duplicate_requirements(self):
        catalog = {role: [option([clue('worlds_final', True)], index, category)
                         for category in (True, False)]
                   for index, role in enumerate(generator.ROLE_ORDER)}
        with self.assertRaisesRegex(ValueError, 'Cannot build'):
            board_factory.choose_board(catalog, StableRandom())

    def test_scheduled_match_is_used_before_the_generic_catalog(self):
        match_module = ModuleType('apps.dailies.match_boards')
        authored = SimpleNamespace(pk=50)
        match_module.store_match_board = Mock(return_value=authored)
        daily = SimpleNamespace()
        with patch.dict(sys.modules, {'apps.dailies.match_boards': match_module}), \
                patch.object(board_factory, 'question_catalog') as catalog:
            self.assertIs(board_factory.store_daily(daily, random.Random(1), {}), authored)
        match_module.store_match_board.assert_called_once_with(daily)
        catalog.assert_not_called()

    def test_procedural_writer_refuses_an_invalid_plan_before_creating_any_slots(self):
        match_module = ModuleType('apps.dailies.match_boards')
        match_module.store_match_board = Mock(return_value=None)
        repeated = [option([clue('birth_country', 'CN')], index, True) for index in range(5)]
        with patch.dict(sys.modules, {'apps.dailies.match_boards': match_module}), \
                patch.object(board_factory, 'question_catalog', return_value={}), \
                patch.object(board_factory, 'choose_board', return_value=(repeated, 2019)), \
                patch.object(generator.DailySlot.objects, 'create') as create:
            with self.assertRaisesRegex(ValueError, 'same requirement'):
                board_factory.store_daily(SimpleNamespace(), random.Random(1), {})
        create.assert_not_called()


class FutureEditorDiversityTests(SimpleTestCase):
    def request(self, target, action):
        data = {'date': target, 'action': action,
                'selections': {role: ['repeated'] for role in generator.ROLE_ORDER}}
        request = RequestFactory().post('/editor/', json.dumps(data), content_type='application/json')
        request.user = SimpleNamespace(is_active=True, is_staff=True, has_perm=lambda _permission: True)
        return request

    def render(self, target, action):
        catalog = {'repeated': clue('birth_country', 'CN')}
        with patch.object(builder.timezone, 'localdate', return_value=date(2026, 11, 3)), \
                patch.object(builder.Daily.objects, 'filter', return_value=SimpleNamespace(first=lambda: None)), \
                patch.object(builder, 'condition_catalog', return_value=catalog), \
                patch.object(builder, 'count_candidates', return_value=[SimpleNamespace(nickname='Example')]), \
                patch.object(builder, 'validate_slots'), \
                patch.object(builder.Daily.objects, 'select_for_update') as write:
            response = builder.builder_view(self.request(target, action), SimpleNamespace())
        return response, write

    def test_future_editor_preview_reports_duplicate_clues_and_publish_cannot_write(self):
        for action, status in [('preview', 200), ('draft', 400), ('publish', 400)]:
            with self.subTest(action=action):
                response, write = self.render('2026-11-04', action)
                self.assertEqual(response.status_code, status)
                payload = json.loads(response.content)
                self.assertIn('same requirement', payload['issues'][0])
                if action == 'preview':
                    self.assertFalse(payload['valid'])
                write.assert_not_called()

    def test_preview_of_existing_today_is_not_retroactively_rejected_by_future_rules(self):
        response, write = self.render('2026-11-03', 'preview')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['valid'])
        write.assert_not_called()


class FutureAdminPublicationDiversityTests(SimpleTestCase):
    def repeated_daily(self, target):
        condition = SimpleNamespace(condition_type='birth_country', operator='eq', value='CN')
        slots = [SimpleNamespace(conditions=SimpleNamespace(all=lambda: [condition])) for _ in range(5)]
        return SimpleNamespace(date=target, status='draft', save=Mock(),
                               slots=SimpleNamespace(prefetch_related=lambda *_args: slots))

    def test_future_publish_action_cannot_bypass_the_editor_guard(self):
        from apps.admin_tools.views import AdminDailyViewSet
        daily = self.repeated_daily(date(2026, 11, 4))
        view = AdminDailyViewSet()
        view.get_object = Mock(return_value=daily)
        with patch('apps.admin_tools.views.timezone.localdate', return_value=date(2026, 11, 3)), \
                patch('apps.admin_tools.views.validate_daily'):
            response = view.publish(SimpleNamespace())
        self.assertEqual(response.status_code, 400)
        self.assertIn('same requirement', response.data['detail'])
        daily.save.assert_not_called()

    def test_status_patch_and_moving_a_published_board_to_future_both_require_diversity(self):
        from apps.admin_tools.views import AdminDailyViewSet
        from rest_framework.exceptions import ValidationError
        for target, status, attrs in [
            (date(2026, 11, 4), 'draft', {'status': 'published'}),
            (date(2026, 11, 3), 'published', {'date': date(2026, 11, 4)}),
        ]:
            with self.subTest(target=target, attrs=attrs):
                daily = self.repeated_daily(target)
                daily.status = status
                serializer = SimpleNamespace(instance=daily, validated_data=attrs, save=Mock())
                with patch('apps.admin_tools.views.timezone.localdate', return_value=date(2026, 11, 3)):
                    with self.assertRaises(ValidationError):
                        AdminDailyViewSet().perform_update(serializer)
                serializer.save.assert_not_called()

    def test_existing_today_can_still_be_published_without_retroactive_rejection(self):
        from apps.admin_tools.views import AdminDailyViewSet
        daily = self.repeated_daily(date(2026, 11, 3))
        serializer = SimpleNamespace(instance=daily, validated_data={'status': 'published'}, save=Mock())
        with patch('apps.admin_tools.views.timezone.localdate', return_value=date(2026, 11, 3)):
            AdminDailyViewSet().perform_update(serializer)
        serializer.save.assert_called_once_with()
