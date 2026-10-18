from datetime import date
from io import StringIO
from itertools import product
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.scoring.models import AnswerStatsDaily
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt

from .generator import generate_daily
from .models import Daily, DailySlot, DailySlotCondition
from .solutions import recommended_roster


TEST_POOL = [
    ('origin', 'easy', 'country', 'eq', 'KR', 'Koreańczyk', 'Korean'),
    ('status', 'medium', 'active', 'eq', True, 'Aktywny', 'Active'),
]
TODAY = date(2026, 10, 18)


class PreparedMonthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.players = [Player.objects.create(
            slug=f'person-{index}', nickname=f'Person {index}', primary_role='top',
            secondary_roles=['jungle', 'mid', 'adc', 'support'], country_code='KR',
            attributes={'worlds_verified': True, 'activity_verified': True},
        ) for index in range(8)]

    @patch('django.utils.timezone.localdate', return_value=TODAY)
    @patch('apps.dailies.generator.build_condition_pool', return_value=TEST_POOL)
    def test_month_is_complete_repeatable_preserves_human_answers_and_hides_future(self, _pool, _today):
        human_board = generate_daily(date=date(2026, 10, 7), seed='existing-human-board')
        human = Submission.objects.create(daily=human_board, guest_token='human')
        human_slot = human_board.slots.first()
        human_answer = SubmissionAnswer.objects.create(
            submission=human, daily_slot=human_slot, player=self.players[0], is_correct=True,
        )
        human_attempt = SubmissionAttempt.objects.create(
            submission=human, daily_slot=human_slot, player=self.players[0], is_correct=True,
        )
        original_conditions = list(human_board.slots.values_list('conditions__pk', 'conditions__condition_type', 'conditions__value'))
        for _ in range(2):
            call_command('prepare_month', month='2026-10', stdout=StringIO())
            self.assertEqual(list(Daily.objects.order_by('date').values_list('date', flat=True)),
                             [date(2026, 10, day) for day in range(1, 32)])
            self.assertEqual(Daily.objects.filter(status='published').count(), 31)
            self.assertEqual(DailySlot.objects.count(), 155)
            self.assertEqual(DailySlotCondition.objects.count(), 310)
            self.assertEqual(Submission.objects.filter(is_seed=True).count(), 0)
            self.assertEqual(SubmissionAnswer.objects.count(), 1)
            self.assertEqual(SubmissionAttempt.objects.count(), 1)
            human_answer.refresh_from_db()
            human_attempt.refresh_from_db()
            self.assertEqual((human_answer.submission_id, human_answer.player_id, human_answer.is_correct),
                             (human.pk, self.players[0].pk, True))
            self.assertEqual(human_attempt.player_id, self.players[0].pk)
            self.assertEqual(list(human_board.slots.values_list('conditions__pk', 'conditions__condition_type', 'conditions__value')),
                             original_conditions)
            snapshot = {
                'boards': list(Daily.objects.order_by('pk').values_list('pk', 'date', 'status')),
                'answers': list(SubmissionAnswer.objects.order_by('pk').values_list(
                    'pk', 'submission_id', 'daily_slot_id', 'player_id', 'points_awarded')),
                'attempts': list(SubmissionAttempt.objects.order_by('pk').values_list('pk', 'player_id')),
            }
            if _ == 0:
                initial = snapshot
            else:
                self.assertEqual(snapshot, initial)
        client = APIClient()
        today = Daily.objects.get(date=TODAY)
        future = Daily.objects.get(date=date(2026, 10, 19))
        future_game = Submission.objects.create(daily=future, guest_token='existing-future-human')
        future_slot = future.slots.first()
        self.assertEqual(client.get('/api/v1/dailies/today/').data['id'], today.pk)
        archive = client.get('/api/v1/dailies/')
        self.assertEqual(archive.data['count'], 18)
        self.assertNotIn(future.pk, [board['id'] for board in archive.data['results']])
        for suffix in ['', 'slots/', 'solutions/', 'answer-stats/', 'score-distribution/']:
            response = client.get(f'/api/v1/dailies/{future.pk}/{suffix}', {'guest_token': future_game.guest_token})
            self.assertEqual(response.status_code, 404, suffix)
        self.assertEqual(client.get('/api/v1/submissions/me/', {'daily_id': future.pk}).status_code, 404)
        self.assertEqual(client.get(f'/api/v1/submissions/{future_game.pk}/',
                                    {'guest_token': future_game.guest_token}).status_code, 404)
        self.assertEqual(client.post('/api/v1/submissions/answer/', {
            'daily_id': future.pk, 'slot_id': future_slot.pk,
            'player_slug': self.players[0].slug, 'guest_token': 'future-human',
        }, format='json').status_code, 400)
        self.assertEqual(client.post('/api/v1/submissions/', {
            'daily_id': future.pk, 'guest_token': 'future-human',
            'answers': [{'slot_id': future_slot.pk, 'player_slug': self.players[0].slug}],
        }, format='json').status_code, 400)
        self.assertFalse(Submission.objects.filter(guest_token='future-human').exists())
        graph = client.get(f'/api/v1/dailies/{today.pk}/score-distribution/')
        self.assertEqual(graph.status_code, 200)
        self.assertEqual((graph.data['total_submissions'], graph.data['seeded_count'], graph.data['real_count']), (0, 0, 0))
        self.assertEqual(client.get('/api/v1/leaderboard/').data['results'], [])
        self.assertFalse(AnswerStatsDaily.objects.exists())
        self.assertEqual(client.get(f'/api/v1/dailies/{today.pk}/solutions/',
                                    {'guest_token': 'retired-test-voter'}).status_code, 403)

    def test_month_command_rejects_synthetic_votes_before_creating_boards(self):
        with self.assertRaisesRegex(CommandError, 'Synthetic votes are disabled'):
            call_command('prepare_month', month='2026-10', voters=10, stdout=StringIO())
        self.assertFalse(Daily.objects.exists())
        self.assertFalse(Submission.objects.exists())

    @patch('django.utils.timezone.localdate', return_value=TODAY)
    @patch('apps.dailies.generator.build_condition_pool', return_value=TEST_POOL)
    def test_authenticated_solutions_ignore_guest_credentials_and_keep_unpicked_candidates(self, _pool, _today):
        board = generate_daily(date=TODAY, seed='auth-solutions')
        board.status = 'published'
        board.save(update_fields=['status'])
        user = get_user_model().objects.create_user(username='owner')
        other = get_user_model().objects.create_user(username='other')
        finished = Submission.objects.create(daily=board, user=user, errors_used=MAX_ERRORS)
        guest = Submission.objects.create(daily=board, guest_token='guest-winner', errors_used=MAX_ERRORS)
        slot = board.slots.first()
        SubmissionAnswer.objects.create(submission=guest, daily_slot=slot, player=self.players[0], is_correct=True)
        url = f'/api/v1/dailies/{board.pk}/solutions/'
        client = APIClient()
        client.force_authenticate(other)
        self.assertEqual(client.get(url, {'guest_token': 'guest-winner'}).status_code, 403)
        client.force_authenticate(user)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([len(result['players']) for result in response.data['slots']], [8] * 5)
        first_slot = response.data['slots'][0]
        self.assertEqual(first_slot['sample_size'], 1)
        self.assertEqual(first_slot['players'][0]['pick_count'], 1)
        self.assertEqual(first_slot['players'][0]['pick_percent'], 100)
        self.assertEqual([player['pick_percent'] for player in first_slot['players'][1:]], [0] * 7)
        for result in response.data['slots'][1:]:
            self.assertEqual(result['sample_size'], 0)
            self.assertTrue(all(player['pick_percent'] == 0 for player in result['players']))
        client.force_authenticate(None)
        self.assertEqual(client.get(url).status_code, 403)
        finished.refresh_from_db()
        self.assertEqual(finished.errors_used, MAX_ERRORS)


class RecommendationVerificationTests(SimpleTestCase):
    def test_top_five_reduction_matches_the_exhaustive_optimum_with_overlapping_candidates(self):
        slots = [{'slot_id': slot, 'players': [
            {'id': player, 'slug': str(player), 'pick_percent': (player * 19 + slot * 13) % 101}
            for player in range(1, 7)
        ]} for slot in range(5)]
        feasible_costs = [sum(player['pick_percent'] for player in roster)
                          for roster in product(*(slot['players'] for slot in slots))
                          if len({player['id'] for player in roster}) == 5]
        for popular, expected in [(True, max(feasible_costs)), (False, min(feasible_costs))]:
            result = recommended_roster(slots, popular)
            self.assertEqual(len(set(result.values())), 5)
            cost = sum(next(player['pick_percent'] for player in slot['players']
                            if player['id'] == result[str(slot['slot_id'])]) for slot in slots)
            self.assertEqual(cost, expected)
