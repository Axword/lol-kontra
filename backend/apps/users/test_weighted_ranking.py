from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily
from apps.submissions.models import Submission


class WeightedRankingTests(TestCase):
    def test_five_game_prior_average_pagination_and_personal_rank(self):
        today = timezone.localdate()
        boards = [Daily.objects.create(date=today - timedelta(days=i), status='published') for i in range(10)]
        # One perfect game should not outrank ten consistently strong games.
        Submission.objects.create(daily=boards[0], guest_token='single-guest-token-123', total_points=0, errors_used=10)
        for board in boards:
            Submission.objects.create(daily=board, guest_token='regular-guest-token-123', total_points=20, errors_used=10)
        for i in range(20):
            Submission.objects.create(daily=boards[0], guest_token=f'other-guest-token-{i:03}', total_points=300, errors_used=10)
        # Unfinished, practice, seed and future scores must not change the prior.
        Submission.objects.create(daily=boards[1], guest_token='single-guest-token-123', total_points=0)
        future = Daily.objects.create(date=today + timedelta(days=1), status='published')
        Submission.objects.create(daily=future, guest_token='single-guest-token-123', total_points=0, errors_used=10)
        client = APIClient()
        payload = {'limit': 10, 'mode': 'weighted', 'guest_token': 'single-guest-token-123'}
        response = client.post('/api/v1/leaderboard/', payload)
        self.assertEqual(response.status_code, 200)
        data = response.data
        average = 6200 / 31
        self.assertAlmostEqual(data['population_average'], average)
        self.assertEqual(data['prior_games'], 5)
        self.assertEqual(data['total_players'], 22)
        self.assertEqual(data['total_pages'], 3)
        self.assertEqual(data['results'][0]['games_played'], 10)
        self.assertAlmostEqual(data['results'][0]['weighted_points'], (200 + 5 * average) / 15)
        self.assertEqual(data['current_player']['rank'], 2)
        second = client.post('/api/v1/leaderboard/', {**payload, 'page': 2}).data
        self.assertEqual([r['rank'] for r in second['results']], list(range(11, 21)))
        self.assertEqual(second['current_player']['rank'], 2)
        last = client.post('/api/v1/leaderboard/', {**payload, 'page': 999}).data
        self.assertEqual(last['page'], 3)
        self.assertEqual([r['rank'] for r in last['results']], [21, 22])
        normal = client.post('/api/v1/leaderboard/', {**payload, 'mode': 'average'}).data
        self.assertEqual(normal['current_player']['rank'], 1)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn(payload['guest_token'], response.content.decode())
        for invalid in ({'page': 0}, {'mode': 'arbitrary'}):
            self.assertEqual(client.post('/api/v1/leaderboard/', {**payload, **invalid}).status_code, 400)
