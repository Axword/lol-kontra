from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.dailies.models import Daily, DailySlot
from apps.players.models import Player
from apps.submissions.models import MAX_ERRORS, Submission, SubmissionAnswer, SubmissionAttempt
from .guest_profiles import guest_stats


class GuestProfileStatsTests(TestCase):
    token = 'profile-stats-v2-guest'

    def setUp(self):
        self.faker = Player.objects.create(slug='faker', nickname='Faker', primary_role='mid', attributes={
            'portrait_source': 'Leaguepedia',
            'portrait_url': 'https://static.wikia.nocookie.net/lolesports_gamepedia_en/images/f/f5/Faker.png',
        })
        self.zeus = Player.objects.create(slug='zeus', nickname='Zeus', primary_role='top')

    def game(self, days_ago=0, roles=('mid',), **kwargs):
        daily = Daily.objects.create(date=timezone.localdate() - timedelta(days=days_ago),
                                     status=kwargs.pop('status', 'published'))
        slots = [DailySlot.objects.create(daily=daily, position=index, role=role)
                 for index, role in enumerate(roles, 1)]
        identity = {'user': kwargs.pop('user')} if 'user' in kwargs else {'guest_token': self.token}
        game = Submission.objects.create(daily=daily, **identity, **kwargs)
        return game, slots

    def answer(self, game, slot, player=None, **kwargs):
        return SubmissionAnswer.objects.create(submission=game, daily_slot=slot,
                                                player=player or self.faker, is_correct=True, **kwargs)

    def attempt(self, game, slot, *, correct, player=None):
        return SubmissionAttempt.objects.create(submission=game, daily_slot=slot,
                                                 player=player or self.faker, is_correct=correct)

    def test_empty_stats_have_no_invented_players_or_activity(self):
        with self.assertNumQueries(1):
            stats = guest_stats(self.token)
        self.assertEqual(stats['correct_answers'], 0)
        self.assertEqual(stats['incorrect_attempts'], 0)
        self.assertEqual(stats['accuracy_percent'], 0)
        self.assertEqual(stats['perfect_games'], 0)
        self.assertEqual(stats['average_pick_percent'], 0)
        self.assertIsNone(stats['most_used_player'])
        self.assertEqual(stats['top_players'], [])

    def test_real_attempts_saved_percentages_and_top_players_use_two_queries(self):
        first, slots = self.game(roles=('mid', 'top'), errors_used=1, total_points=400)
        self.answer(first, slots[0], rarity_percent=10, rarity_tier='rare')
        self.answer(first, slots[1], self.zeus, rarity_percent=None, rarity_tier='legendary')
        self.attempt(first, slots[0], correct=False, player=self.zeus)
        self.attempt(first, slots[0], correct=True)
        self.attempt(first, slots[1], correct=True, player=self.zeus)
        second, second_slots = self.game(1, total_points=300)
        self.answer(second, second_slots[0], rarity_percent=30, rarity_tier='common')
        self.attempt(second, second_slots[0], correct=True)
        with self.assertNumQueries(2):
            stats = guest_stats(self.token)
        self.assertEqual(stats['games_played'], 2)
        self.assertEqual(stats['total_points'], 700)
        self.assertEqual(stats['best_score'], 300)
        self.assertEqual(stats['avg_points'], 350)
        self.assertEqual(stats['correct_answers'], 3)
        self.assertEqual(stats['incorrect_attempts'], 1)
        self.assertEqual(stats['accuracy_percent'], 75)
        self.assertEqual(stats['perfect_games'], 1)
        self.assertEqual(stats['average_pick_percent'], 20)
        self.assertEqual(stats['most_used_player'], {
            'id': self.faker.pk, 'slug': 'faker', 'nickname': 'Faker',
            'portrait_url': self.faker.attributes['portrait_url'], 'pick_count': 2,
        })
        self.assertEqual([row['nickname'] for row in stats['top_players']], ['Faker', 'Zeus'])
        self.assertEqual(stats['top_players'][1]['pick_count'], 1)
        self.assertIsNone(stats['top_players'][1]['portrait_url'])
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.total_points, second.total_points), (400, 300))
        self.assertEqual(SubmissionAttempt.objects.count(), 4)

    def test_legacy_games_only_fall_back_when_their_attempt_history_is_empty(self):
        legacy, slots = self.game(errors_used=3)
        self.answer(legacy, slots[0], rarity_percent=0)
        recorded, recorded_slots = self.game(1, errors_used=4)
        self.answer(recorded, recorded_slots[0], rarity_percent=10)
        self.attempt(recorded, recorded_slots[0], correct=True)
        self.attempt(recorded, recorded_slots[0], correct=False, player=self.zeus)
        stats = guest_stats(self.token)
        self.assertEqual(stats['correct_answers'], 2)
        self.assertEqual(stats['incorrect_attempts'], 4)
        self.assertAlmostEqual(stats['accuracy_percent'], 100 / 3)
        self.assertEqual(stats['average_pick_percent'], 5)
        self.assertEqual(stats['perfect_games'], 0)

    def test_all_new_stats_exclude_incomplete_private_test_and_other_guest_games(self):
        included, slots = self.game(errors_used=MAX_ERRORS, total_points=123)
        self.answer(included, slots[0], rarity_percent=12)
        self.attempt(included, slots[0], correct=True)
        self.attempt(included, slots[0], correct=False, player=self.zeus)
        exclusions = [
            {'is_practice': True, 'is_scored': True},
            {'is_seed': True, 'is_scored': True},
            {'status': 'draft', 'is_scored': True},
            {'user': get_user_model().objects.create_user(username='registered'), 'is_scored': True},
            {'is_scored': True},
        ]
        for day, kwargs in enumerate(exclusions, 1):
            excluded, excluded_slots = self.game(day, **kwargs)
            if day == 5:
                excluded.guest_token = 'another-profile-token'
                excluded.save(update_fields=['guest_token'])
            self.answer(excluded, excluded_slots[0], self.zeus, rarity_percent=90)
            self.attempt(excluded, excluded_slots[0], correct=True, player=self.zeus)
            self.attempt(excluded, excluded_slots[0], correct=False)
        future, future_slots = self.game(-1, is_scored=True)
        self.answer(future, future_slots[0], self.zeus, rarity_percent=90)
        self.attempt(future, future_slots[0], correct=False)
        pending, pending_slots = self.game(6, roles=('mid', 'top'))
        self.answer(pending, pending_slots[0], self.zeus, rarity_percent=90)
        self.attempt(pending, pending_slots[0], correct=False)
        stats = guest_stats(self.token)
        self.assertEqual(stats['games_played'], 1)
        self.assertEqual(stats['correct_answers'], 1)
        self.assertEqual(stats['incorrect_attempts'], 1)
        self.assertEqual(stats['accuracy_percent'], 50)
        self.assertEqual(stats['perfect_games'], 0)
        self.assertEqual(stats['average_pick_percent'], 12)
        self.assertEqual([row['nickname'] for row in stats['top_players']], ['Faker'])

    def test_top_five_order_is_deterministic_and_portraits_are_verified(self):
        self.faker.attributes = {'portrait_source': 'Leaguepedia', 'portrait_url': 'https://evil.test/Faker.png'}
        self.faker.save(update_fields=['attributes'])
        for day, nickname in enumerate(['Zulu', 'Beta', 'Echo', 'Alpha', 'Delta', 'Faker']):
            player = self.faker if nickname == 'Faker' else Player.objects.create(slug=nickname.lower(), nickname=nickname)
            game, slots = self.game(day)
            self.answer(game, slots[0], player)
        with self.assertNumQueries(2):
            stats = guest_stats(self.token)
        self.assertEqual([row['nickname'] for row in stats['top_players']], ['Alpha', 'Beta', 'Delta', 'Echo', 'Faker'])
        self.assertEqual(stats['most_used_player']['nickname'], 'Alpha')
        self.assertIsNone(stats['top_players'][-1]['portrait_url'])

    def test_scored_incomplete_or_empty_board_is_not_a_perfect_game(self):
        incomplete, slots = self.game(roles=('mid', 'top'), is_scored=True)
        self.answer(incomplete, slots[0])
        self.game(1, roles=(), is_scored=True)
        self.assertEqual(guest_stats(self.token)['perfect_games'], 0)
