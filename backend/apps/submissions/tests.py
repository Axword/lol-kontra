from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from .models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt


class GameplayTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slots = []
        for position, role in enumerate(['top', 'mid'], 1):
            slot = DailySlot.objects.create(daily=self.daily, position=position, role=role)
            DailySlotCondition.objects.create(
                slot=slot, condition_type='country', value='KR', label_pl='Korea', label_en='Korea'
            )
            self.slots.append(slot)
        self.right = Player.objects.create(slug='right', nickname='Right', primary_role='top')
        self.mid = Player.objects.create(slug='mid', nickname='Mid', primary_role='mid')
        self.wrong = Player.objects.create(slug='wrong', nickname='Wrong', primary_role='support')
        self.wrong2 = Player.objects.create(slug='wrong2', nickname='Wrong2', primary_role='support')
        self.token = 'guest-one'

    def answer(self, player=None, slot=None, **extra):
        return self.client.post('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk,
            'slot_id': (slot or self.slots[0]).pk,
            'player_slug': (player or self.right).slug,
            'guest_token': self.token,
            **extra,
        }, format='json')

    def test_live_answer_and_resume_use_the_same_server_state(self):
        result = self.answer()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data['is_correct'])
        self.assertEqual(result.data['total_points'], 500)
        state = self.client.get('/api/v1/submissions/me/', {
            'daily_id': self.daily.pk, 'guest_token': self.token,
        })
        self.assertEqual(state.status_code, 200)
        self.assertEqual(state.data['correct_count'], 1)
        self.assertEqual(state.data['total_points'], result.data['total_points'])
        self.assertEqual(state.data['answers'][0]['player_slug'], self.right.slug)

    def test_other_archive_finishes_preserve_all_prior_completed_games_and_picks(self):
        self.daily.date -= timedelta(days=1)
        self.daily.save(update_fields=['date'])
        historical = []
        for finalized, score in [(False, 400), (True, 350)]:
            game = Submission.objects.create(
                daily=self.daily, guest_token=f'completed-{finalized}',
                total_points=score, is_scored=finalized, errors_used=2,
            )
            historical.append(game.pk)
            for slot, player, percent, count in zip(self.slots, [self.right, self.mid], [41.7, 33.3], [417, 333]):
                SubmissionAnswer.objects.create(
                    submission=game, daily_slot=slot, player=player, is_correct=True,
                    rarity_percent=percent, rarity_tier='common', points_awarded=-percent,
                    scoring_pick_count=count, scoring_sample_size=1000,
                )
                SubmissionAttempt.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
            SubmissionAttempt.objects.create(submission=game, daily_slot=self.slots[0],
                                             player=self.wrong, is_correct=False)

        def preserved():
            return {
                'games': list(Submission.objects.filter(pk__in=historical).order_by('pk').values()),
                'answers': list(SubmissionAnswer.objects.filter(submission_id__in=historical).order_by('pk').values()),
                'attempts': list(SubmissionAttempt.objects.filter(submission_id__in=historical).order_by('pk').values()),
            }

        before = preserved()
        for board_status in ['published', 'closed', 'scored']:
            self.daily.status = board_status
            self.daily.save(update_fields=['status'])
            for bulk in [False, True]:
                with self.subTest(status=board_status, bulk=bulk):
                    token = f'new-archive-{board_status}-{bulk}'
                    payload = {'daily_id': self.daily.pk, 'guest_token': token}
                    if bulk:
                        payload['answers'] = [
                            {'slot_id': slot.pk, 'player_slug': player.slug}
                            for slot, player in zip(self.slots, [self.right, self.mid])
                        ]
                        result = self.client.post('/api/v1/submissions/', payload, format='json')
                        self.assertEqual(result.status_code, 201)
                    else:
                        for slot, player in zip(self.slots, [self.right, self.mid]):
                            result = self.client.post('/api/v1/submissions/answer/', {
                                **payload, 'slot_id': slot.pk, 'player_slug': player.slug,
                            }, format='json')
                            self.assertEqual(result.status_code, 200)
                    self.assertEqual(result.data['total_points'], 300)
                    self.assertTrue(result.data['is_over'])
                    self.assertTrue(result.data['is_scored'])
                    self.assertEqual(preserved(), before)

    def test_correct_slot_cannot_be_replaced(self):
        self.answer()
        result = self.answer(self.wrong)
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data['unchanged'])
        self.assertEqual(result.data['player_slug'], self.right.slug)
        self.assertEqual(result.data['errors_used'], 0)
        self.assertEqual(SubmissionAttempt.objects.count(), 1)

    def test_answer_includes_slots_already_solved_in_another_window(self):
        self.answer()
        other_window = APIClient()
        response = other_window.post('/api/v1/submissions/answer/', {
            'daily_id': self.daily.pk, 'slot_id': self.slots[1].pk,
            'player_slug': self.mid.slug, 'guest_token': self.token,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['correct_count'], 2)
        self.assertEqual(len(response.data['answers']), 2)
        self.assertEqual([answer['player_slug'] for answer in response.data['answers']], ['right', 'mid'])
        self.assertTrue(all(answer['is_correct'] for answer in response.data['answers']))

    def test_repeated_miss_does_not_consume_errors_even_after_another_miss(self):
        self.answer(self.wrong)
        self.answer(self.wrong2)
        retry = self.answer(self.wrong)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data['errors_used'], 2)
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(SubmissionAttempt.objects.count(), 2)

    def test_retry_of_final_answer_is_idempotent(self):
        self.answer()
        result = self.answer(self.mid, self.slots[1])
        self.assertTrue(result.data['is_over'])
        retry = self.answer(self.mid, self.slots[1])
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(SubmissionAttempt.objects.count(), 2)

    def test_retry_of_last_miss_does_not_raise_game_over(self):
        submission = Submission.objects.create(daily=self.daily, guest_token=self.token, errors_used=MAX_ERRORS - 1)
        result = self.answer(self.wrong)
        self.assertEqual(result.data['errors_left'], 0)
        retry = self.answer(self.wrong)
        self.assertEqual(retry.status_code, 200)
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(SubmissionAttempt.objects.filter(submission=submission).count(), 1)
        self.assertEqual(self.answer(self.wrong2).status_code, 400)

    def test_invalid_slot_and_player_do_not_create_game_or_consume_errors(self):
        self.assertEqual(self.answer(slot_id=999999).status_code, 400)
        self.assertEqual(self.answer(player_slug='missing').status_code, 400)
        self.assertFalse(Submission.objects.exists())

    def test_guest_token_and_slug_lengths_are_validated(self):
        self.assertEqual(self.answer(guest_token='a' * 65).status_code, 400)
        self.assertEqual(self.answer(player_slug='a' * 81).status_code, 400)

    def test_unpublished_and_future_games_cannot_be_played(self):
        self.daily.status = 'draft'
        self.daily.save()
        self.assertEqual(self.answer().status_code, 400)
        self.daily.status = 'published'
        self.daily.date += timedelta(days=1)
        self.daily.save()
        self.assertEqual(self.answer().status_code, 400)
        self.assertFalse(Submission.objects.exists())

    def test_closed_archive_remains_playable(self):
        self.daily.date -= timedelta(days=1)
        self.daily.status = 'scored'
        self.daily.save()
        result = self.answer()
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.data['is_practice'])
        self.assertTrue(result.data['is_diamond_pick'])

    def test_midnight_preserves_the_same_official_game_and_archive_resume(self):
        first = self.answer()
        official = Submission.objects.get(pk=first.data['submission_id'])
        with patch('django.utils.timezone.localdate', return_value=self.daily.date + timedelta(days=1)):
            state = self.client.get('/api/v1/submissions/me/', {'daily_id': self.daily.pk, 'guest_token': self.token})
            self.assertEqual(state.data['id'], official.pk)
            self.assertFalse(state.data['is_practice'])
            archived = self.answer(self.wrong, self.slots[1])
            self.assertFalse(archived.data['is_practice'])
            self.assertEqual(archived.data['submission_id'], official.pk)
            old = self.client.get('/api/v1/submissions/me/', {
                'daily_id': self.daily.pk, 'guest_token': self.token, 'mode': 'official',
            })
            self.assertEqual(old.data['id'], official.pk)
            self.assertEqual(old.data['total_points'], first.data['total_points'])
            self.assertEqual(old.data['correct_count'], 1)
        official.refresh_from_db()
        self.assertEqual(official.errors_used, 1)
        self.assertEqual(official.answers.get(is_correct=True).player, self.right)

    def test_submission_retrieval_requires_owner(self):
        answer = self.answer()
        url = f"/api/v1/submissions/{answer.data['submission_id']}/"
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(url, {'guest_token': 'wrong-token'}).status_code, 404)
        self.assertEqual(self.client.get(url, {'guest_token': self.token}).status_code, 200)
        self.client.force_authenticate(get_user_model().objects.create_user(username='other'))
        self.assertEqual(self.client.get(url, {'guest_token': self.token}).status_code, 404)

    def test_authenticated_submission_is_private_and_has_no_guest_identity(self):
        user = get_user_model().objects.create_user(username='owner')
        self.client.force_authenticate(user)
        result = self.answer()
        submission = Submission.objects.get(pk=result.data['submission_id'])
        self.assertEqual(submission.user, user)
        self.assertIsNone(submission.guest_token)
        self.assertNotIn('guest_token', result.data)
        url = f'/api/v1/submissions/{submission.pk}/'
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_daily_id_in_resume_is_bad_request(self):
        result = self.client.get('/api/v1/submissions/me/', {'daily_id': 'not-a-number'})
        self.assertEqual(result.status_code, 400)

    def test_diamond_is_permanent_metadata_without_a_point_bonus_after_cache_loss(self):
        first = self.answer()
        cache.clear()
        self.token = 'guest-two'
        second = self.answer()
        self.assertEqual(second.status_code, 200)
        self.assertTrue(first.data['is_diamond_pick'])
        self.assertFalse(second.data['is_diamond_pick'])
        self.assertEqual(second.data['total_points'], 400)

    def test_rolled_back_answer_does_not_pollute_the_pick_population(self):
        with patch('apps.submissions.serializers.compute_rarity', side_effect=RuntimeError('temporary failure')):
            with self.assertRaises(RuntimeError):
                self.answer()
        self.assertFalse(Submission.objects.exists())
        result = self.answer()
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.data['is_diamond_pick'])
        self.assertEqual(result.data['deduction'], 0)

    def test_bulk_submission_rejects_duplicate_slots_and_rolls_back_invalid_answers(self):
        data = {'daily_id': self.daily.pk, 'guest_token': self.token, 'answers': [
            {'slot_id': self.slots[0].pk, 'player_slug': self.right.slug},
            {'slot_id': self.slots[0].pk, 'player_slug': self.wrong.slug},
        ]}
        self.assertEqual(self.client.post('/api/v1/submissions/', data, format='json').status_code, 400)
        data['answers'][1] = {'slot_id': self.slots[1].pk, 'player_slug': 'missing'}
        self.assertEqual(self.client.post('/api/v1/submissions/', data, format='json').status_code, 400)
        self.assertFalse(Submission.objects.exists())

    def test_bulk_submission_returns_new_guest_token_for_resume(self):
        result = self.client.post('/api/v1/submissions/', {
            'daily_id': self.daily.pk,
            'answers': [{'slot_id': self.slots[0].pk, 'player_slug': self.right.slug}],
        }, format='json')
        self.assertEqual(result.status_code, 201)
        self.assertTrue(result.data.get('guest_token'))
        state = self.client.get('/api/v1/submissions/me/', {
            'daily_id': self.daily.pk, 'guest_token': result.data['guest_token'],
        })
        self.assertEqual(state.data['id'], result.data['id'])

    def _multirole_player_and_slots(self):
        self.slots[1].role = 'adc'
        self.slots[1].save(update_fields=['role'])
        self.slots[0].role = 'mid'
        self.slots[0].save(update_fields=['role'])
        self.mid.secondary_roles = ['adc']
        self.mid.save(update_fields=['secondary_roles'])

    def test_same_correct_multirole_player_cannot_fill_two_slots(self):
        self._multirole_player_and_slots()
        first = self.answer(self.mid, self.slots[0])
        self.assertEqual(first.status_code, 200)
        before = self.client.get('/api/v1/submissions/me/', {
            'daily_id': self.daily.pk, 'guest_token': self.token,
        }).data
        repeated = self.answer(self.mid, self.slots[1])
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(str(repeated.data['code']), 'duplicate_player')
        after = self.client.get('/api/v1/submissions/me/', {
            'daily_id': self.daily.pk, 'guest_token': self.token,
        }).data
        self.assertEqual(after, before)
        self.assertEqual(SubmissionAttempt.objects.count(), 1)

    def test_bulk_rejects_duplicate_player_without_creating_game(self):
        self._multirole_player_and_slots()
        response = self.client.post('/api/v1/submissions/', {
            'daily_id': self.daily.pk, 'guest_token': self.token,
            'answers': [{'slot_id': slot.pk, 'player_slug': self.mid.slug} for slot in self.slots],
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Submission.objects.exists())
        self.assertFalse(SubmissionAnswer.objects.exists())
        self.assertFalse(SubmissionAttempt.objects.exists())


class ConcurrentGameplayTests(TransactionTestCase):
    def test_simultaneous_first_answers_award_one_permanent_diamond_and_handle_retries(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections

        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR', label_pl='Korea', label_en='Korea')
        player = Player.objects.create(slug='top', nickname='Top', primary_role='top')
        for tokens in [('one', 'two'), ('three', 'three')]:
            barrier = Barrier(2)

            def submit(token):
                close_old_connections()
                try:
                    barrier.wait(timeout=10)
                    response = APIClient().post('/api/v1/submissions/answer/', {
                        'daily_id': daily.pk, 'slot_id': slot.pk, 'player_slug': player.slug, 'guest_token': token,
                    }, format='json')
                    return response.status_code
                finally:
                    close_old_connections()

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(submit, tokens))
            self.assertEqual(results, [200, 200])
        self.assertEqual(SubmissionAnswer.objects.filter(is_diamond_pick=True).count(), 1)
        self.assertEqual(Submission.objects.count(), 3)
        self.assertEqual(SubmissionAttempt.objects.count(), 3)
