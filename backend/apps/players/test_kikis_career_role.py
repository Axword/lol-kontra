from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import importlib
import io
import json
from pathlib import Path
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from django.db import close_old_connections, connection, connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.dailies.validators import evaluate_condition, player_matches_slot
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt
from .career_roles import _corrections, with_verified_career_roles
from .models import Player
from .test_worlds_import import snapshot
from .worlds_import import build_worlds_players


release = importlib.import_module('apps.players.migrations.0005_worlds_2026_october_19_release')
correction = importlib.import_module('apps.players.migrations.0006_verified_career_roles')


def kikis_record():
    return deepcopy(next(row for row in release.load_release() if row['slug'] == 'kikis'))


class KikisSourceEvidenceTests(unittest.TestCase):
    def test_every_pinned_correction_targets_one_verified_canonical_identity(self):
        records = {row['slug']: row for row in release.load_release()}
        corrections = correction.load_corrections()
        self.assertEqual(len({row['slug'] for row in corrections}), len(corrections))
        self.assertEqual(len({row['leaguepedia_page'] for row in corrections}), len(corrections))
        for row in corrections:
            original = records[row['slug']]
            self.assertTrue(original['attributes']['worlds_verified'])
            self.assertEqual(row['leaguepedia_page'], original['attributes']['leaguepedia_page'])
            self.assertTrue(set(row['roles']))
            self.assertTrue(set(row['roles']) <= {'top', 'jungle', 'mid', 'adc', 'support'})
            self.assertTrue(set(row['roles']) - {original['primary_role'], *original['secondary_roles']})
        faker = with_verified_career_roles(records['faker'])
        self.assertEqual((faker['primary_role'], faker['secondary_roles']), ('mid', []))

    def test_pinned_evidence_proves_top_in_fnatic_and_g2_without_altering_release(self):
        source = next(row for row in correction.load_corrections() if row['slug'] == 'kikis')
        self.assertEqual((source['slug'], source['leaguepedia_page'], source['roles']),
                         ('kikis', 'Kikis', ['top', 'mid', 'support']))
        for team, expected_games in [('Fnatic', 17), ('G2 Esports', 51)]:
            self.assertEqual(sum(row['games'] for row in source['evidence_rows']
                                 if row['team'] == team and row['ingame_role'] == 'Top'), expected_games)
        original = kikis_record()
        self.assertEqual((original['primary_role'], original['secondary_roles']), ('jungle', []))
        updated = with_verified_career_roles(original)
        self.assertEqual(updated['secondary_roles'], ['top', 'mid', 'support'])
        self.assertEqual(original['secondary_roles'], [])
        self.assertEqual(updated['attributes']['worlds_roles'], ['jungle'])
        self.assertEqual(updated['career_stats']['worlds']['games'], 6)

    def test_only_exact_canonical_identity_gets_the_role_and_existing_roles_survive(self):
        record = kikis_record()
        for changed in [dict(slug='different'), dict(attributes={}), dict(attributes={'leaguepedia_page': 'Other'})]:
            other = {**record, **changed}
            self.assertIs(with_verified_career_roles(other), other)
        record['secondary_roles'] = ['support']
        self.assertEqual(with_verified_career_roles(record)['secondary_roles'], ['top', 'mid', 'support'])
        record['primary_role'] = 'top'
        self.assertEqual(with_verified_career_roles(record)['secondary_roles'], ['mid', 'support'])

    def test_tampered_source_fails_before_database_work(self):
        _corrections.cache_clear()
        try:
            with patch.object(Path, 'read_text', return_value='{}'):
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    with_verified_career_roles(kikis_record())
                with self.assertRaisesRegex(ValueError, 'checksum'):
                    correction.load_corrections()
        finally:
            _corrections.cache_clear()

    def test_worlds_refresh_retains_career_top_without_claiming_worlds_top(self):
        data = snapshot()
        # Nick1 occupies the jungle role in this independently validated game.
        data['players'][1].update(page='Kikis', id='Kikis', role='Jungle')
        data['aliases'][1]['page'] = 'Kikis'
        result, _ = build_worlds_players(data, [kikis_record()])
        imported = next(row for row in result if row['slug'] == 'kikis')
        self.assertEqual((imported['primary_role'], imported['secondary_roles']), ('jungle', ['top', 'mid', 'support']))
        self.assertEqual(imported['attributes']['worlds_roles'], ['jungle'])
        self.assertNotIn('top', next(row for row in result if row['nickname'] == 'Nick2')['secondary_roles'])


class KikisRoleCorrectionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.historical_apps = MigrationLoader(connection).project_state([
            ('players', '0005_worlds_2026_october_19_release')
        ]).apps
        cls.editor = SimpleNamespace(connection=connection)

    def setUp(self):
        self.player = Player.objects.create(**kikis_record())
        self.faker = Player.objects.create(**deepcopy(next(row for row in release.load_release() if row['slug'] == 'faker')))
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slot = DailySlot.objects.create(daily=self.daily, role='top', position=1)
        DailySlotCondition.objects.create(slot=self.slot, condition_type='team', value='fnatic')
        DailySlotCondition.objects.create(slot=self.slot, condition_type='worlds_games', operator='lt', value=50)
        self.client = APIClient()

    def install(self):
        correction.install_correction(self.historical_apps, self.editor)
        self.player.refresh_from_db()

    def answer(self, player=None, token='kikis-local-regression'):
        return self.client.post('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk, 'slot_id': self.slot.pk,
            'player_slug': (player or self.player).slug, 'guest_token': token,
        }, format='json')

    def test_actual_release_bug_is_role_only_then_local_api_accepts_kikis(self):
        self.assertTrue(evaluate_condition(self.player, 'team', 'eq', 'fnatic'))
        self.assertTrue(evaluate_condition(self.player, 'worlds_games', 'lt', 50))
        self.assertFalse(player_matches_slot(self.player, self.slot))
        self.install()
        self.assertTrue(player_matches_slot(self.player, self.slot))
        result = self.answer()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data['is_correct'])
        self.assertEqual(result.data['pick_percent'], 0)
        self.assertEqual(result.data['errors_used'], 0)
        self.assertEqual(self.player.attributes['worlds_roles'], ['jungle'])
        self.assertFalse(evaluate_condition(self.player, 'worlds_multi_role', 'gte', 2))
        self.slot.role = 'adc'
        self.assertFalse(player_matches_slot(self.player, self.slot))

    def test_one_map_yellowstar_top_swap_is_rejected_without_rewriting_worlds_facts(self):
        row = deepcopy(next(row for row in release.load_release() if row['slug'] == 'yellowstar'))
        yellowstar = Player.objects.create(**row)
        before = (deepcopy(yellowstar.attributes), deepcopy(yellowstar.career_stats))
        self.assertIn('top', yellowstar.attributes['worlds_roles'])
        self.assertFalse(player_matches_slot(yellowstar, self.slot))
        self.install()
        yellowstar.refresh_from_db()
        self.assertEqual((yellowstar.attributes, yellowstar.career_stats), before)
        result = self.answer(yellowstar, token='yellowstar-official-top-regression')
        self.assertFalse(result.data['is_correct'])

    def test_migration_only_changes_kikis_secondary_roles_and_is_idempotent(self):
        self.answer()
        self.player.secondary_roles = ['support']
        self.player.save(update_fields=['secondary_roles'])
        original_player = Player.objects.filter(pk=self.player.pk).values().get()
        history = {model: list(model.objects.order_by('pk').values())
                   for model in (Submission, SubmissionAnswer, SubmissionAttempt)}
        self.install()
        expected = {**original_player, 'secondary_roles': ['top', 'mid', 'support']}
        self.assertEqual(Player.objects.filter(pk=self.player.pk).values().get(), expected)
        for model, saved in history.items():
            self.assertEqual(list(model.objects.order_by('pk').values()), saved)
        with CaptureQueriesContext(connection) as queries:
            self.install()
        self.assertFalse(any(row['sql'].lstrip().split()[0] in {'UPDATE', 'INSERT', 'DELETE'} for row in queries))

    def test_conflicting_canonical_identity_fails_without_any_player_changes(self):
        self.player.attributes = {'leaguepedia_page': 'Different player'}
        self.player.save(update_fields=['attributes'])
        with self.assertRaisesRegex(ValueError, 'canonical identity: kikis'):
            self.install()
        self.assertEqual(Player.objects.get(pk=self.player.pk).secondary_roles, [])

    def test_all_identity_conflicts_are_checked_before_the_first_write(self):
        claims = [next(row for row in correction.load_corrections() if row['slug'] == 'kikis'),
                  {'slug': 'faker', 'leaguepedia_page': 'Conflicting identity', 'roles': ['top']}]
        with patch.object(correction, 'load_corrections', return_value=claims):
            with CaptureQueriesContext(connection) as queries:
                with self.assertRaisesRegex(ValueError, 'canonical identity: faker'):
                    self.install()
        self.assertFalse(any(row['sql'].lstrip().split()[0] in {'UPDATE', 'INSERT', 'DELETE'} for row in queries))
        self.assertEqual(Player.objects.get(pk=self.player.pk).secondary_roles, [])

    def test_full_seed_replay_cannot_erase_verified_career_top(self):
        self.install()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'players.json'
            path.write_text(json.dumps([kikis_record()]), encoding='utf-8')
            call_command('seed_players', full=True, file=str(path), stdout=io.StringIO())
        self.player.refresh_from_db()
        self.assertEqual(self.player.secondary_roles, ['top', 'mid', 'support'])
        self.assertEqual(self.player.attributes['worlds_roles'], ['jungle'])

    def test_previous_miss_can_be_retried_after_correction_without_erasing_mistake(self):
        first = self.answer()
        self.assertFalse(first.data['is_correct'])
        old_attempt = SubmissionAttempt.objects.values().get()
        self.install()
        result = self.answer()
        self.assertTrue(result.data['is_correct'])
        self.assertFalse(result.data['unchanged'])
        self.assertEqual(result.data['errors_used'], 1)
        self.assertEqual(SubmissionAttempt.objects.filter(pk=old_attempt['id']).values().get(), old_attempt)
        self.assertEqual(SubmissionAttempt.objects.count(), 2)
        retry = self.answer()
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(SubmissionAttempt.objects.count(), 2)

    def test_previous_miss_can_be_corrected_when_last_wrong_card_is_another_player(self):
        self.answer()
        self.answer(self.faker)
        self.install()
        result = self.answer()
        self.assertTrue(result.data['is_correct'])
        self.assertEqual(result.data['errors_used'], 2)
        self.assertEqual(SubmissionAttempt.objects.filter(is_correct=False).count(), 2)

    def test_retry_preserves_other_correct_choices_and_their_saved_percentages(self):
        first = self.answer()
        game = Submission.objects.get(pk=first.data['submission_id'])
        other_slot = DailySlot.objects.create(daily=self.daily, role='mid', position=2)
        saved = SubmissionAnswer.objects.create(submission=game, daily_slot=other_slot,
            player=self.faker, is_correct=True, rarity_percent=12.5, points_awarded=-87.5,
            scoring_pick_count=1, scoring_sample_size=8)
        before = SubmissionAnswer.objects.filter(pk=saved.pk).values().get()
        self.install()
        result = self.answer()
        self.assertTrue(result.data['is_correct'])
        self.assertEqual(SubmissionAnswer.objects.filter(pk=saved.pk).values().get(), before)
        self.assertEqual(result.data['errors_used'], 1)

    def test_wrong_role_faker_stays_wrong_and_retries_do_not_add_errors(self):
        self.slot.conditions.all().delete()
        DailySlotCondition.objects.create(slot=self.slot, condition_type='country', value='KR')
        self.assertTrue(evaluate_condition(self.faker, 'country', 'eq', 'KR'))
        self.install()
        self.assertFalse(player_matches_slot(self.faker, self.slot))
        self.assertFalse(self.answer(self.faker).data['is_correct'])
        retry = self.answer(self.faker)
        self.assertFalse(retry.data['is_correct'])
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(retry.data['errors_used'], 1)
        self.assertEqual(SubmissionAttempt.objects.count(), 1)

    def test_exhausted_or_scored_games_are_not_reopened_by_correction(self):
        for index, final in enumerate([{'errors_used': MAX_ERRORS}, {'is_scored': True}]):
            token = f'kikis-finished-{index}'
            self.player.secondary_roles = []
            self.player.save(update_fields=['secondary_roles'])
            first = self.answer(token=token)
            game = Submission.objects.get(pk=first.data['submission_id'])
            Submission.objects.filter(pk=game.pk).update(**final)
            self.install()
            before = (Submission.objects.filter(pk=game.pk).values().get(),
                      list(SubmissionAttempt.objects.filter(submission=game).values()))
            result = self.answer(token=token)
            self.assertEqual(result.status_code, 400 if 'errors_used' in final else 200)
            self.assertFalse(SubmissionAnswer.objects.get(submission=game).is_correct)
            self.assertEqual(Submission.objects.filter(pk=game.pk).values().get(), before[0])
            self.assertEqual(list(SubmissionAttempt.objects.filter(submission=game).values()), before[1])


class KikisStrictReleaseCheckTests(TestCase):
    def test_every_verified_role_in_the_final_pack_matches_a_slot_without_changing_worlds_facts(self):
        records = {row['slug']: row for row in release.load_release()}
        corrections = correction.load_corrections()
        Player.objects.bulk_create([Player(**records[row['slug']]) for row in corrections])
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        for position, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
            slot = DailySlot.objects.create(daily=daily, role=role, position=position)
            DailySlotCondition.objects.create(slot=slot, condition_type='worlds_games', operator='gt', value=0)
            DailySlotCondition.objects.create(slot=slot, condition_type='worlds_debut_year', operator='lte', value=2026)
        slots = {slot.role: slot for slot in daily.slots.prefetch_related('conditions')}
        apps = MigrationLoader(connection).project_state().apps
        correction.install_correction(apps, SimpleNamespace(connection=connection))
        players = Player.objects.in_bulk([row['slug'] for row in corrections], field_name='slug')
        for row in corrections:
            player = players[row['slug']]
            self.assertEqual((player.attributes, player.career_stats),
                             (records[row['slug']]['attributes'], records[row['slug']]['career_stats']))
            for role in row['roles']:
                with self.subTest(player=player.slug, role=role):
                    from apps.dailies.validators import PlayerFacts
                    self.assertEqual(player_matches_slot(player, slots[role]), role in PlayerFacts(player).roles)

    def test_strict_checker_accepts_only_the_versioned_kikis_role_overlay(self):
        from apps.admin_tools.release_checks import check_release_data

        apps = MigrationLoader(connection).project_state().apps
        editor = SimpleNamespace(connection=connection)
        release.install_release(apps, editor)
        correction.install_correction(apps, editor)
        calendar = importlib.import_module('apps.dailies.migrations._october_2026_release')
        for source in calendar.load_calendar():
            daily = Daily.objects.create(date=source['date'], status=source['status'])
            for row in source['slots']:
                slot = DailySlot.objects.create(daily=daily, position=row['position'], role=row['role'])
                DailySlotCondition.objects.bulk_create([
                    DailySlotCondition(slot=slot, **condition) for condition in row['conditions']])
        self.assertEqual(check_release_data(strict=True)['players'], 882)
        Player.objects.filter(slug='kikis').update(secondary_roles=['top', 'adc'])
        with self.assertRaisesRegex(ValueError, 'differs from release: kikis'):
            check_release_data(strict=True)


class CareerRoleMigrationConcurrencyTests(TransactionTestCase):
    def test_migration_allows_a_concurrent_attempt_to_reference_the_locked_player(self):
        player = Player.objects.create(**kikis_record())
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slot = DailySlot.objects.create(daily=daily, role='top', position=1)
        game = Submission.objects.create(daily=daily, guest_token='local-role-lock-regression')
        locked, release_lock = Event(), Event()

        def migrate_while_open():
            close_old_connections()
            try:
                thread_connection = connections['default']
                apps = MigrationLoader(thread_connection).project_state().apps
                with transaction.atomic():
                    correction.install_correction(apps, SimpleNamespace(connection=thread_connection))
                    locked.set()
                    if not release_lock.wait(10):
                        raise RuntimeError('Local migration concurrency test timed out')
            finally:
                connections['default'].close()

        def save_attempt():
            close_old_connections()
            try:
                # Autocommit must also validate the Player FK before returning,
                # while the migration still holds its role update lock.
                return SubmissionAttempt.objects.create(submission_id=game.pk,
                    daily_slot_id=slot.pk, player_id=player.pk, is_correct=False).pk
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            migrating = pool.submit(migrate_while_open)
            try:
                self.assertTrue(locked.wait(10))
                saved = pool.submit(save_attempt)
                attempt_pk = saved.result(timeout=5)
                self.assertTrue(SubmissionAttempt.objects.filter(pk=attempt_pk).exists())
                self.assertFalse(release_lock.is_set())
            finally:
                release_lock.set()
            migrating.result(timeout=10)
        self.assertEqual(Player.objects.get(pk=player.pk).secondary_roles, ['top', 'mid', 'support'])
