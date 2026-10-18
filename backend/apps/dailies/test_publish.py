from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Daily, DailySlot, DailySlotCondition


class PublishRequirementsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user(username='editor', is_staff=True))

    def board(self, number):
        daily = Daily.objects.create(date=date(2026, 10, number))
        for position, role in enumerate(('top', 'jungle', 'mid', 'adc', 'support'), 1):
            slot = DailySlot.objects.create(daily=daily, position=position, role=role)
            for order in range(number):
                DailySlotCondition.objects.create(slot=slot, condition_type='worlds_games', operator='gt',
                                                  value=order + 1, order=order)
        return daily

    def test_publish_action_and_direct_status_update_require_exactly_two_conditions(self):
        for number in (1, 2, 3):
            daily = self.board(number)
            for route in ('action', 'patch'):
                with self.subTest(conditions=number, route=route):
                    response = (self.client.post(f'/api/v1/admin/dailies/{daily.id}/publish/') if route == 'action'
                                else self.client.patch(f'/api/v1/admin/dailies/{daily.id}/', {'status': 'published'}))
                    self.assertEqual(response.status_code, 200 if number == 2 else 400)
                    daily.refresh_from_db()
                    self.assertEqual(daily.status, 'published' if number == 2 else 'draft')
