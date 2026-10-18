"""Saved answers keep their player portrait on resume, without autocomplete."""
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.players.models import Player


class SavedPortraitTests(TestCase):
    def test_correct_answer_and_resumed_game_include_player_portrait(self):
        client = APIClient()
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slots = [DailySlot.objects.create(daily=daily, position=index + 1, role=role)
                 for index, role in enumerate(['top', 'mid'])]
        for slot in slots:
            DailySlotCondition.objects.create(slot=slot, condition_type='country', operator='eq',
                                              value='KR', label_pl='Korea', label_en='Korea')
        portrait = 'https://static.wikia.nocookie.net/lolesports_gamepedia/images/saved-player.png'
        player = Player.objects.create(slug='saved-portrait', nickname='Saved', primary_role='top',
                                       country_code='KR', attributes={'portrait_source': 'Leaguepedia', 'portrait_url': portrait})
        payload = {'daily_id': daily.pk, 'slot_id': slots[0].pk,
                   'player_slug': player.slug, 'guest_token': 'portrait-review-guest'}
        answer = client.post('/api/v1/submissions/answer/', payload, format='json')
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.data['is_correct'])
        self.assertFalse(answer.data['is_over'])
        self.assertEqual(answer.data['player_portrait_url'], portrait)
        saved = client.get('/api/v1/submissions/me/', {'daily_id': daily.pk, 'guest_token': payload['guest_token']})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.data['answers'][0]['player_portrait_url'], portrait)
