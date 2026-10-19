from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt
from apps.users.guest_profiles import guest_display_name, guest_identity_key
from apps.users.models import GuestProfile
from .community import validate_comment
from .generator import CONDITION_POOL, build_condition_pool
from .models import CommunityComment, Daily, DailySlot
from .roster_images import MAX_ROSTER_BYTES, load_player_portrait, render_roster_png
from .validators import evaluate_condition


class DailyCommunityTests(TestCase):
    token = 'community-viewer-guest-1234'
    other_token = 'community-author-guest-5678'

    def setUp(self):
        self.client = APIClient()
        self.daily = Daily.objects.create(date=timezone.localdate(), status='published')
        self.slots = [DailySlot.objects.create(daily=self.daily, position=index, role=role)
                      for index, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1)]
        self.players = [Player.objects.create(slug=f'player-{index}', nickname=f'Player{index}', primary_role=slot.role)
                        for index, slot in enumerate(self.slots)]
        self.url = f'/api/v1/dailies/{self.daily.pk}/community/'
        patcher = patch('apps.dailies.roster_images.load_player_portrait', return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def game(self, token=None, *, count=5, score=25, **kwargs):
        identity = {'user': kwargs.pop('user')} if 'user' in kwargs else {'guest_token': token or self.token}
        game = Submission.objects.create(daily=self.daily, total_points=score, **identity, **kwargs)
        for index, slot in enumerate(self.slots[:count]):
            SubmissionAnswer.objects.create(submission=game, daily_slot=slot, player=self.players[index],
                                             is_correct=True, rarity_percent=index,
                                             rarity_tier='legendary' if index < 2 else 'rare')
        return game

    def post(self, token=None, **payload):
        return self.client.post(self.url, {'guest_token': token or self.token, **payload}, format='json')

    def test_author_defaults_and_metadata_are_public_without_revealing_solutions(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['author'], {
            'name': 'Axword', 'url': 'https://x.com/AxwordLol', 'description': 'Autor wyzwania',
        })
        self.assertFalse(response.data['can_view_solutions'])
        self.assertFalse(response.data['can_comment'])
        self.assertIsNone(response.data['own_comment_id'])
        self.assertEqual(response.data['comments'], [])
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_completed_player_can_post_an_actual_png_roster_and_cannot_spoof_saved_data(self):
        game = self.game(score=17)
        response = self.post(comment='Świetna plansza! Faker był trudny.', score=-500,
                             roster_image_url='https://evil.test/fake.png', roster_png='fake')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['can_view_solutions'])
        self.assertFalse(response.data['can_comment'])
        row = response.data['comments'][0]
        self.assertEqual(row['score'], 17)
        self.assertEqual(row['nickname'], guest_display_name(self.token))
        self.assertEqual(row['text'], 'Świetna plansza! Faker był trudny.')
        self.assertEqual(response.data['own_comment_id'], row['id'])
        comment = CommunityComment.objects.get()
        self.assertEqual(comment.submission_id, game.pk)
        self.assertTrue(bytes(comment.roster_png).startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertLessEqual(len(comment.roster_png), MAX_ROSTER_BYTES)
        image_response = self.client.get(row['roster_image_url'])
        self.assertEqual(image_response.status_code, 200)
        self.assertEqual(image_response['Content-Type'], 'image/png')
        self.assertIn('immutable', image_response['Cache-Control'])
        self.assertEqual(image_response['X-Content-Type-Options'], 'nosniff')
        with Image.open(BytesIO(image_response.content)) as image:
            self.assertEqual(image.size, (720, 500))
        game.refresh_from_db()
        self.assertEqual(game.total_points, 17)
        self.assertEqual(SubmissionAttempt.objects.count(), 0)
        self.assertNotIn(self.token, response.content.decode())
        self.assertNotIn(guest_identity_key(self.token), response.content.decode())

    def test_reposts_are_idempotent_and_text_edits_preserve_the_immutable_snapshot(self):
        self.game()
        first = self.post(comment='Dobry skład.').data['comments'][0]
        snapshot = bytes(CommunityComment.objects.get().roster_png)
        with patch('apps.dailies.community.render_roster_png') as render:
            repeated = self.post(comment='Dobry skład.').data['comments'][0]
            changed = self.post(comment='Jeszcze lepszy skład!').data['comments'][0]
            render.assert_not_called()
        self.assertEqual(CommunityComment.objects.count(), 1)
        self.assertEqual(first['id'], repeated['id'])
        self.assertEqual(first['roster_image_url'], changed['roster_image_url'])
        self.assertEqual(bytes(CommunityComment.objects.get().roster_png), snapshot)
        self.assertEqual(changed['text'], 'Jeszcze lepszy skład!')

    def test_text_and_roster_urls_stay_hidden_until_viewer_actually_finishes(self):
        self.game(self.other_token)
        original = self.post(self.other_token, comment='Faker na midzie.').data['comments'][0]
        for response in [self.client.get(self.url), self.post()]:
            self.assertFalse(response.data['can_view_solutions'])
            self.assertIsNone(response.data['comments'][0]['text'])
            self.assertIsNone(response.data['comments'][0]['roster_image_url'])
            self.assertNotIn(original['roster_image_url'], response.content.decode())
        unfinished = self.game(count=1, is_scored=True)
        self.assertFalse(self.post().data['can_view_solutions'])
        self.assertEqual(self.post(comment='Spoiler').status_code, 403)
        unfinished.errors_used = MAX_ERRORS
        unfinished.save(update_fields=['errors_used'])
        revealed = self.post().data
        self.assertTrue(revealed['can_view_solutions'])
        self.assertTrue(revealed['can_comment'])
        self.assertEqual(revealed['comments'][0]['text'], 'Faker na midzie.')
        self.assertEqual(revealed['comments'][0]['roster_image_url'], original['roster_image_url'])

    def test_practice_seed_unfinished_and_other_guest_cannot_publish_for_someone_else(self):
        self.game(self.other_token)
        for kwargs in [{'count': 5, 'is_practice': True}, {'count': 5, 'is_seed': True}, {'count': 1}]:
            with self.subTest(kwargs=kwargs):
                game = self.game(**kwargs)
                self.assertEqual(self.post(comment='Mój skład.').status_code, 403)
                game.delete()
        self.assertEqual(CommunityComment.objects.count(), 0)

    def test_future_and_unpublished_daily_and_its_image_remain_inaccessible(self):
        self.game()
        image_url = self.post(comment='Zapisany skład.').data['comments'][0]['roster_image_url']
        for updates in [dict(status='draft'), dict(status='published', date=timezone.localdate() + timedelta(days=1))]:
            for key, value in updates.items():
                setattr(self.daily, key, value)
            self.daily.save(update_fields=list(updates))
            self.assertEqual(self.client.get(self.url).status_code, 404)
            self.assertEqual(self.post(comment='Nie teraz').status_code, 404)
            self.assertEqual(self.client.get(image_url).status_code, 404)

    def test_comment_moderation_is_atomic_and_allows_normal_punctuation(self):
        self.game()
        original = self.post(comment='Super! 5/5, dzięki.\nNastępna jutro?')
        self.assertEqual(original.status_code, 200)
        for text in ['kurwa', 'f u c k', 'xxkurwaxx', 'A' * 501, 'hello\u202eworld', 123, None, ['text']]:
            with self.subTest(text=text):
                response = self.post(comment=text)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn('comment', response.data)
                self.assertEqual(CommunityComment.objects.get().text, 'Super! 5/5, dzięki.\nNastępna jutro?')

    def test_bad_guest_token_cannot_read_private_solution_content(self):
        for token in ['short', 'contains spaces 1234', 'x' * 65, 123]:
            self.assertEqual(self.post(token).status_code, 400)

    def test_rankings_use_lower_scores_top_ten_and_team_averages_once_per_player(self):
        for index, score in enumerate([10, 30, 5, *range(40, 50)]):
            token = f'community-ranking-guest-{index:04}'
            self.game(token, score=score)
            GuestProfile.objects.create(guest_key=guest_identity_key(token), nickname=f'Fan{index}',
                                        supported_team='t1' if index < 2 else 'g2' if index == 2 else '')
        self.game('excluded-seed-token', score=0, is_seed=True)
        self.game('excluded-practice-token', score=0, is_practice=True)
        self.game('excluded-incomplete-token', score=0, count=1)
        registered = get_user_model().objects.create_user(username='Registered')
        self.game(user=registered, score=2)
        response = self.client.get(self.url)
        players = response.data['player_ranking']
        self.assertEqual(len(players), 10)
        self.assertEqual([row['score'] for row in players[:4]], [2, 5, 10, 30])
        self.assertEqual(players[0]['nickname'], 'Registered')
        self.assertIsNone(players[0]['team'])
        teams = response.data['team_ranking']
        self.assertEqual([(row['team']['id'], row['players'], row['average_score']) for row in teams],
                         [('g2', 1, 5), ('t1', 2, 20)])
        self.assertNotIn('guest_token', response.content.decode())
        self.assertNotIn('community-ranking-guest', response.content.decode())

    def test_custom_author_fields_are_used(self):
        self.daily.author_name = 'Editor'
        self.daily.author_url = 'https://example.org/editor'
        self.daily.author_description = 'Autor planszy'
        self.daily.save()
        self.assertEqual(self.client.get(self.url).data['author'], {
            'name': 'Editor', 'url': 'https://example.org/editor', 'description': 'Autor planszy',
        })

    def test_binary_snapshot_has_a_database_size_limit(self):
        game = self.game()
        with self.assertRaises(IntegrityError), transaction.atomic():
            CommunityComment.objects.create(submission=game, roster_png=b'x' * (MAX_ROSTER_BYTES + 1))

    def test_diamond_saved_zero_is_rendered_without_recalculating_popularity(self):
        game = self.game(score=0)
        answer = game.answers.get(daily_slot=self.slots[0])
        answer.is_diamond_pick = True
        answer.save(update_fields=['is_diamond_pick'])
        value = render_roster_png(game)
        with Image.open(BytesIO(value)) as image:
            self.assertEqual(image.getpixel((22, 70)), (221, 246, 255))
        answer.refresh_from_db()
        self.assertEqual(answer.rarity_percent, 0)
        self.assertTrue(answer.is_diamond_pick)


class CommunityPortraitSafetyTests(TestCase):
    def trusted_player(self):
        return Player(attributes={
            'portrait_source': 'Leaguepedia',
            'portrait_url': 'https://static.wikia.nocookie.net/lolesports/photo.png',
        })

    def test_unverified_or_foreign_portraits_never_trigger_network_requests(self):
        for attributes in [
            {'portrait_url': 'https://static.wikia.nocookie.net/photo.png'},
            {'portrait_source': 'Leaguepedia', 'portrait_url': 'https://evil.test/photo.png'},
            {'portrait_source': 'Leaguepedia', 'portrait_url': 'http://127.0.0.1/photo.png'},
        ]:
            player = Player(attributes=attributes)
            with patch('apps.dailies.roster_images.httpx.stream') as stream:
                self.assertIsNone(load_player_portrait(player))
                stream.assert_not_called()

    def test_verified_portrait_is_bounded_decoded_and_redirects_are_not_followed(self):
        picture = BytesIO()
        Image.new('RGB', (64, 64), '#ffffff').save(picture, format='PNG')
        response = MagicMock(status_code=200)
        response.iter_bytes.return_value = [picture.getvalue()]
        context = MagicMock()
        context.__enter__.return_value = response
        with patch('apps.dailies.roster_images.httpx.stream', return_value=context) as stream:
            image = load_player_portrait(self.trusted_player())
        self.assertEqual(image.size, (42, 48))
        self.assertFalse(stream.call_args.kwargs['follow_redirects'])
        response.status_code = 302
        response.iter_bytes.reset_mock()
        with patch('apps.dailies.roster_images.httpx.stream', return_value=context):
            self.assertIsNone(load_player_portrait(self.trusted_player()))
        response.iter_bytes.assert_not_called()

    def test_oversized_or_corrupt_portrait_uses_a_safe_fallback(self):
        for value in [b'not an image', b'x' * 1_000_001]:
            response = MagicMock(status_code=200)
            response.iter_bytes.return_value = [value]
            context = MagicMock()
            context.__enter__.return_value = response
            with patch('apps.dailies.roster_images.httpx.stream', return_value=context):
                self.assertIsNone(load_player_portrait(self.trusted_player()))

    def test_removed_generator_requirement_still_validates_historical_slots(self):
        self.assertNotIn(('worlds_debut_year', 'gte', 2020), {(entry[2], entry[3], entry[4])
                           for entry in CONDITION_POOL if not isinstance(entry[4], dict)})
        self.assertFalse(any(entry[2:5] == ('worlds_debut_year', 'gte', 2020)
                             for entry in build_condition_pool([])))
        player = Player(attributes={'worlds_appearances': [2021]})
        self.assertTrue(evaluate_condition(player, 'worlds_debut_year', 'gte', 2020))
