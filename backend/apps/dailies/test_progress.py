from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from .models import Daily, DailySlot


class ChallengeProgressTests(TestCase):
    def test_private_markers_distinguish_finished_unfinished_other_players_and_unreleased_boards(self):
        token = 'own-guest-token-123456'
        player = Player.objects.create(slug='faker', nickname='Faker')
        boards = [Daily.objects.create(date=timezone.localdate() - timedelta(days=i), status='published') for i in range(5)]
        for board in boards:
            for i, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
                DailySlot.objects.create(daily=board, position=i, role=role)
        finished = Submission.objects.create(daily=boards[0], guest_token=token, errors_used=10)
        unfinished = Submission.objects.create(daily=boards[1], guest_token=token)
        SubmissionAnswer.objects.create(submission=unfinished, daily_slot=boards[1].slots.first(), player=player, is_correct=True)
        Submission.objects.create(daily=boards[2], guest_token='someone-else-123456', errors_used=10)
        Submission.objects.create(daily=boards[3], guest_token=token, is_seed=True, errors_used=10)
        boards[4].status = 'draft'; boards[4].save()
        Submission.objects.create(daily=boards[4], guest_token=token, errors_used=10)
        client = APIClient()
        response = client.post('/api/v1/dailies/progress/', {'guest_token': token})
        self.assertEqual(response.status_code, 200)
        markers = {row['daily_id']: row['completed'] for row in response.data['results']}
        self.assertEqual(markers, {finished.daily_id: True, unfinished.daily_id: False})
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertNotIn(token, response.content.decode())
        self.assertEqual(client.post('/api/v1/dailies/progress/', {}).data['results'], [])
        self.assertEqual(client.post('/api/v1/dailies/progress/', {'guest_token': 'invalid'}).status_code, 400)

    def test_five_correct_answers_finish_board_and_authenticated_identity_wins(self):
        user = get_user_model().objects.create_user(username='player')
        board = Daily.objects.create(date=timezone.localdate(), status='published')
        game = Submission.objects.create(daily=board, user=user)
        for i, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
            slot = DailySlot.objects.create(daily=board, position=i, role=role)
            player = Player.objects.create(slug=f'p-{i}', nickname=f'P{i}')
            SubmissionAnswer.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
        client = APIClient(); client.force_authenticate(user)
        self.assertEqual(client.post('/api/v1/dailies/progress/', {'guest_token': 'other-guest-token-123456'}).data['results'],
                         [{'daily_id': board.pk, 'completed': True}])
