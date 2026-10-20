from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.players.models import Player
from .generator import ROLE_ORDER, validate_daily
from .models import Daily, DailySlot, DailySlotCondition


class PublishRequirementsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user(username='editor', is_staff=True))

    def board(self, count=10, author='', minimum=10):
        daily = Daily.objects.create(date=timezone.localdate() + timedelta(days=1), author_name=author, minimum_candidates=minimum)
        for position, role in enumerate(ROLE_ORDER, 1):
            slot = DailySlot.objects.create(daily=daily, position=position, role=role)
            DailySlotCondition.objects.create(slot=slot, condition_type='worlds_final', operator='eq', value=True)
            for index in range(count):
                Player.objects.create(slug=f'{role}-{index}', nickname=f'{role}-{index}', primary_role=role,
                                      attributes={'worlds_finals': [2020]})
        return daily

    def test_publish_and_direct_status_update_enforce_ten_combined_answers(self):
        daily = self.board(count=9)
        for route in ('action', 'patch'):
            response = (self.client.post(f'/api/v1/admin/dailies/{daily.id}/publish/') if route == 'action'
                        else self.client.patch(f'/api/v1/admin/dailies/{daily.id}/', {'status': 'published'}))
            self.assertEqual(response.status_code, 400)
            daily.refresh_from_db()
            self.assertEqual(daily.status, 'draft')

    def test_ten_answers_can_be_published(self):
        daily = self.board()
        for route in ('action', 'patch'):
            response = (self.client.post(f'/api/v1/admin/dailies/{daily.id}/publish/') if route == 'action'
                        else self.client.patch(f'/api/v1/admin/dailies/{daily.id}/', {'status': 'published'}))
            self.assertEqual(response.status_code, 200)

    def test_guest_board_is_an_explicit_exception(self):
        daily = self.board(count=2, author='Kaczy')
        self.assertEqual(self.client.post(f'/api/v1/admin/dailies/{daily.id}/publish/').status_code, 200)

    def test_historical_board_keeps_previous_candidate_policy(self):
        daily = self.board(count=7, minimum=None)
        self.assertEqual(validate_daily(daily), daily)

    def test_duplicate_requirements_still_rejected(self):
        daily = self.board()
        for slot in daily.slots.all():
            DailySlotCondition.objects.create(slot=slot, condition_type='worlds_final', operator='eq', value=True, order=1)
        self.assertEqual(self.client.post(f'/api/v1/admin/dailies/{daily.id}/publish/').status_code, 400)
