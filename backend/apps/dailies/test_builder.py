import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.players.models import Player
from apps.submissions.models import Submission
from .builder import condition_key
from .generator import ROLE_ORDER
from .models import Daily

FINAL = ('final', 'medium', 'worlds_final', 'eq', True, 'Grał w finale Worlds', 'Played a Worlds final')
COUNTRY = ('origin', 'easy', 'country', 'eq', 'KR', 'Koreańczyk', 'Korean')
LOST_FINAL = ('lost_final', 'medium', 'worlds_final_lost', 'eq', True,
              'Przegrał finał Worlds', 'Lost a Worlds final')
TITLE = ('title', 'medium', 'worlds_titles_min', 'gte', 1, 'Wygrał Worlds', 'Won Worlds')
DEBUT_TITLE = ('debut_title', 'medium', 'worlds_title_on_debut', 'eq', True,
               'Wygrał Worlds na debiucie', 'Won Worlds on debut')
BOARD_CLUES = [FINAL, LOST_FINAL, TITLE, COUNTRY, DEBUT_TITLE]
PLAYER_FACTS = {'worlds_finals': [2020, 2021], 'worlds_titles': [2020],
                'worlds_appearances': [2020, 2021]}


class BoardBuilderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='owner', password='test-only')
        self.client.force_login(self.user)
        self.url = reverse('admin:dailies_daily_builder')
        self.payload = {'date': str(timezone.localdate() + timedelta(days=1)), 'action': 'preview',
                        'selections': {role: [condition_key(clue)] for role, clue in zip(ROLE_ORDER, BOARD_CLUES)}}
        self.catalog = patch('apps.dailies.builder.condition_catalog',
                             return_value={condition_key(clue): clue for clue in BOARD_CLUES})
        self.catalog.start()
        self.addCleanup(self.catalog.stop)

    def players(self, count):
        for role in ROLE_ORDER:
            for index in range(count):
                Player.objects.create(slug=f'{role}-{index}', nickname=f'{role}-{index}', primary_role=role,
                                      country_code='KR', attributes=PLAYER_FACTS.copy())

    def post(self, **changes):
        return self.client.post(self.url, data=json.dumps({**self.payload, **changes}), content_type='application/json')

    def test_editor_requires_staff_permissions_and_csrf(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        staff = get_user_model().objects.create_user(username='limited', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url, data='{}', content_type='application/json').status_code, 403)

    def test_preview_lists_actual_answers_without_creating_daily(self):
        self.players(10)
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['valid'])
        self.assertEqual(response.json()['slots']['top']['count'], 10)
        self.assertIn('top-0', response.json()['slots']['top']['players'])
        self.assertFalse(Daily.objects.filter(date=self.payload['date']).exists())

    def test_nine_combined_answers_cannot_be_saved_or_published(self):
        self.players(9)
        for action in ('draft', 'publish'):
            self.assertEqual(self.post(action=action).status_code, 400)
        self.assertFalse(Daily.objects.filter(date=self.payload['date']).exists())

    def test_guest_can_publish_below_ten_and_reopen_exact_choices(self):
        self.players(2)
        response = self.post(action='publish', author_name='Kaczy', author_url='https://x.com/kaczy102')
        self.assertEqual(response.status_code, 200)
        daily = Daily.objects.get(date=self.payload['date'])
        self.assertEqual(daily.minimum_candidates, 10)
        self.assertEqual(daily.author_name, 'Kaczy')
        page = self.client.get(response.json()['url'])
        self.assertContains(page, 'Edytor reguł')
        self.assertContains(page, condition_key(FINAL))

    def test_saves_draft_then_publishes_and_preserves_slot_ids(self):
        self.players(10)
        self.assertEqual(self.post(action='draft').status_code, 200)
        daily = Daily.objects.get(date=self.payload['date'])
        ids = list(daily.slots.values_list('pk', flat=True))
        self.assertEqual(daily.status, 'draft')
        self.assertEqual(self.post(action='publish').status_code, 200)
        daily.refresh_from_db()
        self.assertEqual(daily.status, 'published')
        self.assertEqual(list(daily.slots.values_list('pk', flat=True)), ids)

    def test_started_and_archived_board_cannot_be_changed(self):
        self.players(10)
        self.post(action='publish')
        daily = Daily.objects.get(date=self.payload['date'])
        before = list(daily.slots.values_list('conditions__id', flat=True))
        Submission.objects.create(daily=daily, guest_token='keep-game')
        self.assertEqual(self.post(action='draft', author_name='Other').status_code, 400)
        self.assertEqual(list(daily.slots.values_list('conditions__id', flat=True)), before)
        daily.refresh_from_db()
        self.assertEqual(daily.author_name, '')
        self.assertEqual(daily.status, 'published')
        self.assertEqual(self.post(action='publish', date=str(timezone.localdate() - timedelta(days=1))).status_code, 400)

    def test_rejects_unknown_rules_duplicates_and_unsafe_author_url(self):
        self.players(10)
        for changes in ({'selections': {r: ['made-up'] for r in ROLE_ORDER}},
                        {'selections': {r: [condition_key(FINAL)] * 2 for r in ROLE_ORDER}},
                        {'author_url': 'javascript:alert(1)'}):
            self.assertEqual(self.post(action='publish', **changes).status_code, 400)
        self.assertFalse(Daily.objects.filter(date=self.payload['date']).exists())

    def test_distinct_roster_required_even_for_guest(self):
        Player.objects.create(slug='solo', nickname='Solo', primary_role='mid', secondary_roles=ROLE_ORDER,
                              country_code='KR', attributes=PLAYER_FACTS.copy())
        self.assertEqual(self.post(action='publish', author_name='Guest').status_code, 400)
