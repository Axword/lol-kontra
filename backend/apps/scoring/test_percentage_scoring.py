from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt
from .engine import recalc_submission_total, score_daily
from .models import AnswerStatsDaily


class PercentageScoringTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slots = []
        self.players = []
        for index, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
            slot = DailySlot.objects.create(daily=self.daily, position=index, role=role)
            DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR')
            self.slots.append(slot)
            self.players.append(Player.objects.create(slug=role, nickname=role, primary_role=role))
        self.other = Player.objects.create(slug='other', nickname='Other', primary_role='top')

    def answer(self, token='one', index=0, player=None):
        return self.client.post('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk, 'slot_id': self.slots[index].pk,
            'player_slug': (player or self.players[index]).slug, 'guest_token': token,
        }, format='json')

    def population(self, selected, total):
        for index in range(total):
            sub = Submission.objects.create(daily=self.daily, guest_token=f'population-{index}')
            SubmissionAnswer.objects.create(submission=sub, daily_slot=self.slots[0],
                                           player=self.players[0] if index < selected else self.other,
                                           is_correct=True)

    def test_empty_state_starts_at_500_and_first_zero_percent_pick_replaces_one_missing_cost(self):
        state = self.client.get('/api/v1/submissions/me/', {'daily_id': self.daily.pk, 'guest_token': 'one'})
        self.assertEqual(state.data['total_points'], 500)
        self.assertEqual(state.data['slots_total'], 5)
        self.assertEqual(state.data['unfilled_deduction'], 500)
        result = self.answer()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['total_points'], 400)
        self.assertEqual(result.data['pick_percent'], 0)
        self.assertEqual(result.data['deduction'], 100)
        self.assertEqual(result.data['points_awarded'], -100)
        self.assertTrue(result.data['is_provisional'])
        self.assertTrue(result.data['is_diamond_pick'])

    def test_one_percent_means_one_point_not_a_tier_or_diamond_bonus(self):
        self.population(selected=1, total=100)
        result = self.answer()
        self.assertEqual(result.data['sample_size'], 100)
        self.assertEqual(result.data['pick_count'], 1)
        self.assertEqual(result.data['pick_percent'], 1)
        self.assertEqual(result.data['deduction'], 99)
        self.assertEqual(result.data['points_awarded'], -99)
        self.assertEqual(result.data['total_points'], 401)

    def test_fractional_share_and_retry_remain_fixed_until_final_scoring(self):
        self.population(selected=1, total=3)
        first = self.answer()
        self.assertAlmostEqual(first.data['pick_percent'], 100 / 3)
        self.assertAlmostEqual(first.data['deduction'], 100 - 100 / 3)
        self.assertAlmostEqual(first.data['total_points'], 400 + 100 / 3, places=5)
        self.answer('another')
        retry = self.answer()
        for key in ['pick_percent', 'deduction', 'pick_count', 'sample_size', 'total_points']:
            self.assertEqual(retry.data[key], first.data[key], key)
        self.assertTrue(retry.data['unchanged'])
        self.daily.date -= timedelta(days=1)
        self.daily.status = 'closed'
        self.daily.save()
        score_daily(self.daily.pk)
        saved = Submission.objects.get(pk=first.data['submission_id'])
        self.assertEqual(saved.answers.get().points_awarded, -40)
        self.assertEqual(saved.total_points, 460)  # 60% plus four missing positions at 100 each.
        self.assertEqual(saved.answers.get().scoring_sample_size, 5)
        self.assertEqual(SubmissionAttempt.objects.filter(submission=saved).count(), 1)

    def test_exhausting_errors_penalizes_each_unfilled_slot_once(self):
        first = self.answer()
        sub = Submission.objects.get(pk=first.data['submission_id'])
        sub.errors_used = MAX_ERRORS - 1
        sub.save(update_fields=['errors_used'])
        wrong = Player.objects.create(slug='wrong', nickname='Wrong', primary_role='top')
        result = self.answer(index=1, player=wrong)
        self.assertTrue(result.data['is_over'])
        self.assertEqual(result.data['total_points'], 400)
        self.assertEqual(result.data['unfilled_deduction'], 400)
        self.assertEqual(self.answer(index=1, player=wrong).data['total_points'], 400)
        sub.refresh_from_db()
        self.assertEqual(recalc_submission_total(sub), 400)

    def test_full_hundred_percent_roster_keeps_the_worst_score_of_500(self):
        for index, slot in enumerate(self.slots):
            previous = Submission.objects.create(daily=self.daily, guest_token=f'prior-{index}')
            SubmissionAnswer.objects.create(submission=previous, daily_slot=slot,
                                           player=self.players[index], is_correct=True)
            response = self.answer(index=index)
            self.assertEqual(response.data['total_points'], 500)
            self.assertEqual(response.data['pick_percent'], 100)
            self.assertEqual(response.data['deduction'], 0)
        self.assertTrue(response.data['is_over'])
        self.assertEqual(response.data['unfilled_deduction'], 0)

    def test_five_saved_choices_one_two_three_four_five_finish_at_fifteen(self):
        population = [Submission.objects.create(daily=self.daily, guest_token=f'full-voter-{index}')
                      for index in range(100)]
        answers = []
        for selected, (slot, player) in enumerate(zip(self.slots, self.players), 1):
            alternative = Player.objects.create(slug=f'alternative-{slot.role}', nickname=f'Alt {slot.role}',
                                                primary_role=slot.role)
            answers.extend(SubmissionAnswer(submission=game, daily_slot=slot, is_correct=True,
                                            player=player if index < selected else alternative)
                           for index, game in enumerate(population))
        SubmissionAnswer.objects.bulk_create(answers)
        for index, expected in enumerate([401, 303, 206, 110, 15]):
            result = self.answer(index=index)
            self.assertEqual(result.data['pick_percent'], index + 1)
            self.assertEqual(result.data['total_points'], expected)
        self.assertTrue(result.data['is_over'])
        self.assertEqual(sum(answer['rarity_percent'] for answer in result.data['answers']), 15)
        self.assertEqual(result.data['unfilled_deduction'], 0)

    def test_five_first_ever_choices_finish_at_zero_and_wrong_or_missing_slots_cannot_beat_them(self):
        miss = self.answer('miss-only', index=1, player=self.other)
        self.assertFalse(miss.data['is_correct'])
        self.assertEqual(miss.data['total_points'], 500)
        self.assertEqual(miss.data['unfilled_deduction'], 500)
        for index in range(5):
            result = self.answer('perfect-first', index=index)
            self.assertEqual(result.data['pick_percent'], 0)
            self.assertEqual(result.data['total_points'], 400 - index * 100)
        self.assertTrue(result.data['is_over'])
        self.assertEqual(result.data['total_points'], 0)
        self.assertTrue(all(answer['points_awarded'] == -100 for answer in result.data['answers']))
        loser = Submission.objects.get(guest_token='miss-only')
        loser.errors_used = MAX_ERRORS
        loser.save(update_fields=['errors_used'])
        self.assertEqual(recalc_submission_total(loser), 500)
        resumed = self.client.get('/api/v1/submissions/me/', {
            'daily_id': self.daily.pk, 'guest_token': 'perfect-first',
        })
        self.assertEqual(resumed.data['total_points'], 0)

    def test_recalculation_uses_saved_percentages_and_counts_missing_positions_once(self):
        game = Submission.objects.create(daily=self.daily, guest_token='stored-values', errors_used=MAX_ERRORS)
        SubmissionAnswer.objects.create(submission=game, daily_slot=self.slots[0], player=self.players[0],
                                        is_correct=True, rarity_percent=2.5, points_awarded=0)
        SubmissionAnswer.objects.create(submission=game, daily_slot=self.slots[1], player=self.other,
                                        is_correct=False)
        self.assertEqual(recalc_submission_total(game), 402.5)
        self.assertEqual(recalc_submission_total(game), 402.5)

    def test_archive_choices_join_population_without_rewriting_earned_scores(self):
        self.population(selected=1, total=4)
        self.daily.date -= timedelta(days=1)
        self.daily.status = 'closed'
        self.daily.save()
        score_daily(self.daily.pk)
        self.daily.status = 'scored'
        self.daily.save()
        before = list(AnswerStatsDaily.objects.values('player_id', 'pick_count', 'pick_percent'))
        result = self.answer('archive-one')
        self.assertFalse(result.data['is_practice'])
        self.assertEqual(result.data['pick_percent'], 25)
        self.assertEqual(result.data['deduction'], 75)
        self.assertEqual(result.data['total_points'], 425)
        for index in range(1, 5):
            result = self.answer('archive-one', index=index)
        self.assertTrue(result.data['is_over'])
        self.assertEqual(result.data['deduction'], 100)
        self.assertEqual(result.data['total_points'], 25)  # 25% first choice, then four first-ever choices.
        self.assertTrue(result.data['is_scored'])
        self.assertEqual(list(AnswerStatsDaily.objects.values('player_id', 'pick_count', 'pick_percent')), before)
        self.assertEqual(AnswerStatsDaily.objects.filter(daily_slot=self.slots[0]).count(), 2)
        self.assertEqual(Submission.objects.get(guest_token='population-0').total_points, 425)
        ranking = self.client.get('/api/v1/leaderboard/', {'daily_id': self.daily.pk})
        self.assertEqual(len(ranking.data['results']), 5)
        self.assertFalse(Submission.objects.filter(is_practice=True).exists())
        # A new archive choice sees the latest real votes, not the old 25%
        # batch snapshot, while the completed entrant keeps the earned 25.
        later = self.answer('archive-two')
        self.assertEqual((later.data['pick_percent'], later.data['sample_size']), (40, 5))
        self.assertEqual(later.data['total_points'], 440)
        self.assertEqual(Submission.objects.get(guest_token='archive-one').total_points, 25)
        self.assertEqual(Submission.objects.get(guest_token='population-0').total_points, 425)

    def test_retired_seed_votes_never_affect_percent_chart_statistics_or_ranking(self):
        from django.contrib.auth import get_user_model
        from apps.users.services import refresh_user_stats

        user = get_user_model().objects.create_user(username='seed-user')
        seed = Submission.objects.create(daily=self.daily, guest_token='seed-test-voter', is_seed=True)
        for slot, player in zip(self.slots, self.players):
            SubmissionAnswer.objects.create(submission=seed, daily_slot=slot, player=player, is_correct=True)
        score_daily(self.daily.pk, finalize=False)
        result = self.answer()
        self.assertEqual(result.data['pick_percent'], 0)
        self.assertEqual(result.data['deduction'], 100)
        self.assertEqual(result.data['sample_size'], 0)
        self.assertEqual(result.data['total_points'], 400)
        graph = self.client.get(f'/api/v1/dailies/{self.daily.pk}/score-distribution/')
        self.assertEqual(graph.data['total_submissions'], 0)
        self.assertEqual(graph.data['seeded_count'], 0)
        self.assertEqual(graph.data['real_count'], 0)
        self.assertEqual(graph.data['distribution'], [])
        self.assertFalse(AnswerStatsDaily.objects.exists())
        stats = self.client.get(f'/api/v1/dailies/{self.daily.pk}/answer-stats/').data['results']
        self.assertEqual(len(stats), 1)
        self.assertEqual((stats[0]['pick_count'], stats[0]['pick_percent']), (1, 100))
        self.assertEqual(refresh_user_stats(user.pk).games_played, 0)
        self.assertEqual(self.client.get('/api/v1/leaderboard/').data['results'], [])

    def test_rebuilding_current_or_future_seeds_never_finalizes_unfinished_games(self):
        for offset in [0, 1]:
            with self.subTest(offset=offset):
                self.daily.date = timezone.localdate() + timedelta(days=offset)
                self.daily.save()
                sub = Submission.objects.create(daily=self.daily, guest_token=f'not-finished-{offset}')
                score_daily(self.daily.pk, finalize=True)
                sub.refresh_from_db()
                self.assertFalse(sub.is_scored)
                self.assertEqual(sub.total_points, 500)

    def test_archive_practice_api_mode_is_retired(self):
        self.daily.date -= timedelta(days=1)
        self.daily.save()
        response = self.client.get('/api/v1/submissions/me/', {
            'daily_id': self.daily.pk, 'guest_token': 'one', 'mode': 'practice',
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.answer().data['is_practice'], False)

    def test_migration_preserves_answers_and_converts_only_unambiguous_practice_games(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        from django.db import connection

        official = Submission.objects.create(daily=self.daily, guest_token='same', is_scored=True)
        collision = Submission.objects.create(daily=self.daily, guest_token='same', is_practice=True, is_scored=True)
        converted = Submission.objects.create(daily=self.daily, guest_token='unique', is_practice=True, is_scored=True)
        for sub, player in [(official, self.players[0]), (collision, self.other), (converted, self.other)]:
            SubmissionAnswer.objects.create(submission=sub, daily_slot=self.slots[0], player=player,
                                           is_correct=True, is_diamond_pick=sub == official, points_awarded=-10)
        before = list(SubmissionAnswer.objects.order_by('pk').values_list('pk', 'submission_id', 'player_id'))
        migration = import_module('apps.submissions.migrations.0004_percentage_scoring')
        migration.convert_scores(apps, SimpleNamespace(connection=connection))
        official.refresh_from_db()
        collision.refresh_from_db()
        converted.refresh_from_db()
        self.assertFalse(converted.is_practice)
        self.assertTrue(collision.is_practice)
        self.assertFalse(official.is_practice)
        self.assertEqual(list(SubmissionAnswer.objects.order_by('pk').values_list('pk', 'submission_id', 'player_id')), before)
        self.assertEqual(official.total_points, 50)
        self.assertEqual(converted.total_points, 50)
        self.assertEqual(sum(AnswerStatsDaily.objects.values_list('pick_count', flat=True)), 2)
        self.assertFalse(SubmissionAnswer.objects.filter(is_diamond_pick=True).exists())
        self.assertFalse(SubmissionAnswer.objects.filter(points_awarded__gt=0).exists())

    def test_archival_own_score_failure_rolls_back_the_final_answer(self):
        from unittest.mock import patch

        self.daily.date -= timedelta(days=1)
        self.daily.status = 'scored'
        self.daily.save()
        for index in range(4):
            self.answer(index=index)
        before = list(SubmissionAnswer.objects.order_by('pk').values('pk', 'points_awarded', 'rarity_percent'))
        with patch('apps.submissions.serializers.recalc_submission_total', side_effect=RuntimeError('own score failed')):
            with self.assertRaises(RuntimeError):
                self.answer(index=4)
        self.assertEqual(list(SubmissionAnswer.objects.order_by('pk').values('pk', 'points_awarded', 'rarity_percent')), before)
        self.assertEqual(SubmissionAttempt.objects.count(), 4)
        self.assertFalse(Submission.objects.get(guest_token='one').is_scored)


class ConcurrentPercentageScoringTests(TransactionTestCase):
    def test_two_archive_players_finish_different_last_slots_without_partial_commits(self):
        daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=1), status='scored')
        slots, choices = [], []
        for index, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
            slot = DailySlot.objects.create(daily=daily, position=index, role=role)
            DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR')
            slots.append(slot)
            choices.append([Player.objects.create(slug=f'{role}-{side}', nickname=f'{role}-{side}',
                                                  primary_role=role) for side in range(2)])
        games = [Submission.objects.create(daily=daily, guest_token=token) for token in ['first', 'second']]
        last_indices = [4, 0]
        for side, game in enumerate(games):
            for index, slot in enumerate(slots):
                if index == last_indices[side]:
                    continue
                SubmissionAnswer.objects.create(submission=game, daily_slot=slot,
                                                player=choices[index][side], is_correct=True,
                                                rarity_percent=0, points_awarded=-100)
                SubmissionAttempt.objects.create(submission=game, daily_slot=slot,
                                                 player=choices[index][side], is_correct=True)
        barrier = Barrier(2)

        def finish(side):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                last = last_indices[side]
                result = APIClient().post('/api/v1/submissions/answer/', {
                    'daily_id': daily.pk, 'slot_id': slots[last].pk,
                    'player_slug': choices[last][side].slug, 'guest_token': games[side].guest_token,
                }, format='json')
                return result.status_code, result.data.get('is_over')
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(finish, side) for side in range(2)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(results, [(200, True), (200, True)])
        self.assertEqual(SubmissionAnswer.objects.count(), 10)
        self.assertEqual(SubmissionAttempt.objects.count(), 10)
        self.assertEqual(AnswerStatsDaily.objects.count(), 0)
        for game in games:
            game.refresh_from_db()
            self.assertTrue(game.is_scored)
            self.assertEqual(game.total_points, 0)
            self.assertEqual(game.answers.filter(is_correct=True).count(), 5)
            self.assertEqual(list(game.answers.values_list('points_awarded', flat=True)), [-100] * 5)
            self.assertEqual(game.answers.filter(scoring_sample_size=0).count(), 4)
            self.assertEqual(game.answers.filter(scoring_sample_size=1).count(), 1)
        for side, game in enumerate(games):
            last = last_indices[side]
            retry = self.client.post('/api/v1/submissions/answer/', {
                'daily_id': daily.pk, 'slot_id': slots[last].pk,
                'player_slug': choices[last][side].slug, 'guest_token': game.guest_token,
            }, format='json')
            self.assertEqual(retry.status_code, 200)
            self.assertTrue(retry.data['unchanged'])
            self.assertEqual(retry.data['total_points'], 0)
        self.assertEqual(SubmissionAttempt.objects.count(), 10)

    def test_serialized_first_votes_have_zero_then_full_penalty_and_retry_is_idempotent(self):
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR')
        player = Player.objects.create(slug='top', nickname='Top', primary_role='top')
        barrier = Barrier(2)

        def submit(token):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                result = APIClient().post('/api/v1/submissions/answer/', {
                    'daily_id': daily.pk, 'slot_id': slot.pk, 'player_slug': player.slug, 'guest_token': token,
                }, format='json')
                return result.status_code, result.data['deduction']
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, ['one', 'two']))
        self.assertEqual(sorted(results), [(200, 0), (200, 100)])
        self.assertEqual(Submission.objects.count(), 2)
        self.assertEqual(SubmissionAttempt.objects.count(), 2)
        self.assertEqual(SubmissionAnswer.objects.filter(is_diamond_pick=True).count(), 1)
