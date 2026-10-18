from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt


class InitialOfficialPickApiTests(TestCase):
    """Earned percentages use previous real choices and survive later entrants."""

    def setUp(self):
        self.client = APIClient()
        self.players = [
            Player.objects.create(slug=f'initial-top-{index}', nickname=f'Top {index}', primary_role='top')
            for index in range(2)
        ]
        self.wrong = Player.objects.create(slug='initial-support', nickname='Support', primary_role='support')

    def post_answer(self, daily, slot, token, player, *, bulk):
        payload = {'daily_id': daily.pk, 'guest_token': token}
        answer = {'slot_id': slot.pk, 'player_slug': player.slug}
        if bulk:
            payload['answers'] = [answer]
        else:
            payload.update(answer)
        response = self.client.post(
            '/api/v1/submissions/' if bulk else '/api/v1/submissions/answer/', payload, format='json',
        )
        self.assertEqual(response.status_code, 201 if bulk else 200, response.data)
        return response.data

    def add_ignored_population(self, daily, slot):
        for index, player in enumerate(self.players):
            for kind in ['seed', 'practice', 'wrong']:
                game = Submission.objects.create(
                    daily=daily, guest_token=f'{kind}-{index}',
                    is_seed=kind == 'seed', is_practice=kind == 'practice',
                )
                correct = kind != 'wrong'
                SubmissionAnswer.objects.create(
                    submission=game, daily_slot=slot, player=player, is_correct=correct,
                )
                SubmissionAttempt.objects.create(
                    submission=game, daily_slot=slot, player=player, is_correct=correct,
                )

    def check_sequence(self, *, bulk, noisy):
        # Archive publication/scoring status must not switch ordinary gameplay
        # to an inclusive final-population snapshot.
        for days_ago, status in [(0, 'published'), (1, 'published'), (2, 'closed'), (3, 'scored')]:
            with self.subTest(bulk=bulk, noisy=noisy, days_ago=days_ago, status=status):
                daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=days_ago), status=status)
                slot = DailySlot.objects.create(daily=daily, role='top', position=1)
                DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR')
                if noisy:
                    self.add_ignored_population(daily, slot)
                    miss = self.post_answer(daily, slot, 'real-miss', self.wrong, bulk=bulk)
                    self.assertFalse(miss['answers'][0]['is_correct'])
                    self.assertFalse(miss['answers'][0]['is_diamond_pick'])

                saved_states = []
                for token, player, percent, total, diamond, picked, sample in [
                    ('first', self.players[0], 0, 500, True, 0, 0),
                    ('second', self.players[0], 100, 400, False, 1, 1),
                    ('third-new-player', self.players[1], 0, 500, True, 0, 2),
                ]:
                    result = self.post_answer(daily, slot, token, player, bulk=bulk)
                    answer = result['answers'][0]
                    self.assertTrue(answer['is_correct'])
                    self.assertEqual(answer['rarity_percent'], percent)
                    self.assertEqual(answer['points_awarded'], -percent)
                    self.assertEqual(answer['deduction'], percent)
                    self.assertEqual(answer['is_diamond_pick'], diamond)
                    self.assertEqual(result['total_points'], total)
                    if not bulk:
                        self.assertEqual(result['pick_percent'], percent)
                        self.assertEqual(result['rarity_percent'], percent)
                        self.assertEqual(result['pick_count'], picked)
                        self.assertEqual(result['sample_size'], sample)
                    stored = SubmissionAnswer.objects.get(pk=answer['id'])
                    self.assertEqual((stored.scoring_pick_count, stored.scoring_sample_size), (picked, sample))
                    self.assertEqual(stored.diamond_awarded_at is not None, diamond)
                    saved_states.append((token, result, Submission.objects.filter(pk=stored.submission_id).values().get(),
                                         SubmissionAnswer.objects.filter(pk=stored.pk).values().get()))

                # Later guests change the public popularity, never an earlier
                # guest's earned percentage, total, progress or persisted sample.
                for token, initial, game_before, answer_before in saved_states:
                    resumed = self.client.get('/api/v1/submissions/me/', {
                        'daily_id': daily.pk, 'guest_token': token,
                    })
                    self.assertEqual(resumed.status_code, 200)
                    self.assertEqual(resumed.data['total_points'], initial['total_points'])
                    self.assertEqual(resumed.data['answers'], initial['answers'])
                    self.assertEqual(Submission.objects.filter(pk=game_before['id']).values().get(), game_before)
                    self.assertEqual(SubmissionAnswer.objects.filter(pk=answer_before['id']).values().get(), answer_before)

    def test_single_choices_start_zero_then_use_previous_real_choices(self):
        self.check_sequence(bulk=False, noisy=False)

    def test_bulk_choices_start_zero_then_use_previous_real_choices(self):
        self.check_sequence(bulk=True, noisy=False)

    def test_single_choices_ignore_seed_practice_and_wrong_population(self):
        self.check_sequence(bulk=False, noisy=True)

    def test_bulk_choices_ignore_seed_practice_and_wrong_population(self):
        self.check_sequence(bulk=True, noisy=True)
