from datetime import timedelta
import importlib
from types import SimpleNamespace

from django.db import IntegrityError, connection, transaction
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from .diamonds import award_first_pick
from .engine import compute_rarity, score_daily
from .models import AnswerStatsDaily, ScoringConfig


first_pick_migration = importlib.import_module('apps.scoring.migrations.0006_uncommon_and_permanent_first_picks')


class PermanentDiamondTests(TestCase):
    def setUp(self):
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slot = DailySlot.objects.create(daily=self.daily, role='top', position=1)
        DailySlotCondition.objects.create(slot=self.slot, condition_type='country', value='KR')
        self.player = Player.objects.create(slug='first-top', nickname='Top', primary_role='top')
        self.client = APIClient()

    def answer(self, token):
        return self.client.post('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk, 'slot_id': self.slot.pk,
            'player_slug': self.player.slug, 'guest_token': token,
        }, format='json')

    def test_first_pick_stays_diamond_after_later_guests_retries_and_explicit_rescoring(self):
        first = self.answer('first')
        self.assertTrue(first.data['is_diamond_pick'])
        self.assertEqual(first.data['total_points'], 500)
        saved = SubmissionAnswer.objects.get(submission_id=first.data['submission_id'])
        awarded_at = saved.diamond_awarded_at
        self.assertEqual(awarded_at, SubmissionAttempt.objects.get(submission=saved.submission).created_at)
        second = self.answer('second')
        self.assertFalse(second.data['is_diamond_pick'])
        self.assertEqual(second.data['total_points'], 400)
        retry = self.answer('first')
        self.assertTrue(retry.data['is_diamond_pick'])
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(SubmissionAttempt.objects.count(), 2)
        saved.is_diamond_pick = False  # A stale in-memory object cannot erase the stored metadata.
        compute_rarity(saved)
        score_daily(self.daily.pk, finalize=False)
        saved.refresh_from_db()
        self.assertEqual(saved.rarity_percent, 100)
        self.assertTrue(saved.is_diamond_pick)
        self.assertEqual(saved.diamond_awarded_at, awarded_at)
        self.assertEqual(SubmissionAnswer.objects.filter(is_diamond_pick=True).count(), 1)

    def test_practice_seed_and_wrong_attempts_cannot_claim_or_block_the_first_real_pick(self):
        for token, practice, seed, correct in [('practice', True, False, True),
                                                ('seed', False, True, True), ('wrong', False, False, False)]:
            game = Submission.objects.create(daily=self.daily, guest_token=token, is_practice=practice, is_seed=seed)
            answer = SubmissionAnswer.objects.create(submission=game, daily_slot=self.slot,
                                                     player=self.player, is_correct=correct)
            self.assertFalse(award_first_pick(answer))
            answer.refresh_from_db()
            self.assertFalse(answer.is_diamond_pick)
        first = self.answer('real-first')
        self.assertTrue(first.data['is_diamond_pick'])
        self.assertEqual(first.data['deduction'], 0)
        self.assertEqual(SubmissionAnswer.objects.filter(is_diamond_pick=True).count(), 1)

    def test_bulk_first_pick_has_the_same_permanent_metadata(self):
        first = self.client.post('/api/v1/submissions/', {
            'daily_id': self.daily.pk, 'guest_token': 'bulk-first',
            'answers': [{'slot_id': self.slot.pk, 'player_slug': self.player.slug}],
        }, format='json')
        self.assertEqual(first.status_code, 201)
        self.assertTrue(first.data['answers'][0]['is_diamond_pick'])
        self.assertFalse(self.answer('later-single').data['is_diamond_pick'])

    def test_database_rejects_a_second_claim_even_when_bypassing_the_helper(self):
        self.answer('first')
        game = Submission.objects.create(daily=self.daily, guest_token='direct-second')
        with self.assertRaises(IntegrityError), transaction.atomic():
            SubmissionAnswer.objects.create(
                submission=game, daily_slot=self.slot, player=self.player, is_correct=True,
                is_diamond_pick=True, diamond_awarded_at=timezone.now(),
            )


class FirstPickMigrationTests(TestCase):
    def test_backfill_uses_success_chronology_and_fallback_without_changing_points_or_progress(self):
        now = timezone.now()
        daily = Daily.objects.create(date=timezone.localdate())
        slot = DailySlot.objects.create(daily=daily, role='top', position=1)
        players = [Player.objects.create(slug=f'migration-{i}', nickname=str(i)) for i in range(2)]
        ScoringConfig.objects.create()
        records = []

        def historical(token, player, submitted_days, success_days=None, practice=False, seed=False):
            game = Submission.objects.create(daily=daily, guest_token=token, total_points=400,
                                             errors_used=2, is_practice=practice, is_seed=seed)
            Submission.objects.filter(pk=game.pk).update(submitted_at=now+timedelta(days=submitted_days))
            answer = SubmissionAnswer.objects.create(
                submission=game, daily_slot=slot, player=player, is_correct=True,
                rarity_percent=20, rarity_tier='common', points_awarded=-20,
                scoring_pick_count=1, scoring_sample_size=5,
            )
            if success_days is not None:
                attempt = SubmissionAttempt.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
                SubmissionAttempt.objects.filter(pk=attempt.pk).update(created_at=now+timedelta(days=success_days))
            records.append(answer)
            return answer

        old_session = historical('old-session-late-success', players[0], -10, -1)
        winner = historical('later-session-first-success', players[0], -6, -3)
        historical('same-time-later-attempt-id', players[0], -9, -3)
        historical('ignored-practice', players[0], -30, -29, practice=True)
        historical('ignored-seed', players[0], -40, -39, seed=True)
        fallback = historical('no-attempt', players[1], -8)
        historical('later-actual-success', players[1], -10, -7)
        SubmissionAnswer.objects.filter(pk=old_session.pk).update(is_diamond_pick=True, diamond_awarded_at=now)
        snapshot = AnswerStatsDaily.objects.create(daily_slot=slot, player=players[0], pick_count=1,
                                                  pick_percent=20, rarity_tier='common')
        allowed = {'is_diamond_pick', 'diamond_awarded_at', 'rarity_tier'}

        def preserved():
            return {
                'games': list(Submission.objects.order_by('pk').values()),
                'answers': [{key: value for key, value in row.items() if key not in allowed}
                            for row in SubmissionAnswer.objects.order_by('pk').values()],
                'attempts': list(SubmissionAttempt.objects.order_by('pk').values()),
                'snapshots': [{key: value for key, value in row.items() if key != 'rarity_tier'}
                              for row in AnswerStatsDaily.objects.order_by('pk').values()],
            }
        before = preserved()
        historical_apps = MigrationLoader(connection).project_state([
            ('scoring', '0006_uncommon_and_permanent_first_picks'),
        ]).apps
        for _ in range(2):
            first_pick_migration.install_first_pick_metadata(historical_apps, SimpleNamespace(connection=connection))
            self.assertEqual(preserved(), before)
            self.assertEqual(set(SubmissionAnswer.objects.filter(is_diamond_pick=True).values_list('pk', flat=True)),
                             {winner.pk, fallback.pk})
            winner.refresh_from_db()
            fallback.refresh_from_db()
            snapshot.refresh_from_db()
            self.assertEqual(winner.diamond_awarded_at, now+timedelta(days=-3))
            self.assertEqual(fallback.diamond_awarded_at, now+timedelta(days=-8))
            self.assertEqual(snapshot.rarity_tier, 'uncommon')
            self.assertTrue(all(tier == 'uncommon' for tier in SubmissionAnswer.objects.values_list('rarity_tier', flat=True)))
