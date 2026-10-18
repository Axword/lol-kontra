from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from .models import Daily, DailySlot, DailySlotCondition
from .solutions import recommended_roster


class CompletedSolutionsTests(TestCase):
    def setUp(self):
        self.board = Daily.objects.create(date=timezone.localdate(), status='published')
        self.players = [Player.objects.create(slug=f'person-{index}', nickname=f'Person {index}',
            primary_role='top', secondary_roles=['jungle', 'mid', 'adc', 'support'], country_code='KR',
            attributes={'worlds_verified': True, 'activity_verified': True}) for index in range(8)]
        self.slots = []
        for position, role in enumerate(('top', 'jungle', 'mid', 'adc', 'support'), 1):
            slot = DailySlot.objects.create(daily=self.board, position=position, role=role)
            for order, (kind, value) in enumerate((('country', 'KR'), ('active', True))):
                DailySlotCondition.objects.create(slot=slot, condition_type=kind, operator='eq', value=value,
                                                  label_pl=kind, label_en=kind, order=order)
            self.slots.append(slot)
        self.client = APIClient()

    def submission(self, token, count=5, seed=False):
        submission = Submission.objects.create(daily=self.board, guest_token=token, is_seed=seed)
        for slot, player in zip(self.slots[:count], self.players):
            SubmissionAnswer.objects.create(submission=submission, daily_slot=slot, player=player, is_correct=True)
        return submission

    def test_solutions_require_own_finished_game_and_seed_tokens_do_not_unlock_them(self):
        self.submission('winner')
        self.submission('partial', count=1)
        self.submission('seed', seed=True)
        url = f'/api/v1/dailies/{self.board.id}/solutions/'
        for token in ('missing', 'partial', 'seed', ''):
            self.assertEqual(self.client.get(url, {'guest_token': token}).status_code, 403)
        response = self.client.get(url, {'guest_token': 'winner'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([len(slot['players']) for slot in response.data['slots']], [8] * 5)
        self.assertEqual(len(set(response.data['popular'].values())), 5)
        self.assertEqual(len(set(response.data['rare'].values())), 5)
        self.board.date += timedelta(days=1)
        self.board.save()
        self.assertEqual(self.client.get(url, {'guest_token': 'winner'}).status_code, 404)

    def test_recommendation_optimizes_share_without_reusing_a_multirole_player(self):
        slots = [{'slot_id': index, 'players': [
            {'id': player, 'slug': str(player), 'pick_percent': 90 if player == 1 else 10 if player == index + 2 else 0}
            for player in range(1, 9)]} for index in range(5)]
        common = recommended_roster(slots, True)
        self.assertEqual(len(set(common.values())), 5)
        score = sum(next(player['pick_percent'] for player in slot['players'] if player['id'] == common[str(slot['slot_id'])]) for slot in slots)
        self.assertEqual(score, 130)
        rare = recommended_roster(slots, False)
        self.assertEqual(len(set(rare.values())), 5)
        self.assertEqual(sum(next(player['pick_percent'] for player in slot['players'] if player['id'] == rare[str(slot['slot_id'])]) for slot in slots), 0)
