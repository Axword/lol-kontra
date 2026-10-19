from copy import deepcopy
import importlib
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.dailies.models import Daily, DailySlot
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt
from .models import Player


release = importlib.import_module('apps.players.migrations.0005_worlds_2026_october_19_release')


class October19PlayerReleaseTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.historical_apps = MigrationLoader(connection).project_state([('players', '0004_player_integrity_constraints')]).apps
        cls.editor = SimpleNamespace(connection=connection)

    def test_pinned_release_has_updated_worlds_careers_and_playin_outcomes_without_network(self):
        with patch('apps.players.management.commands.seed_players.Command.handle', side_effect=AssertionError('runtime importer called')):
            release.install_release(self.historical_apps, self.editor)
        self.assertEqual(Player.objects.count(), 882)
        verified = list(Player.objects.filter(attributes__worlds_verified=True))
        self.assertEqual(len(verified), 738)
        self.assertEqual(sum(player.attributes.get('portrait_status') == 'available' for player in verified), 733)
        self.assertEqual(sum(player.attributes['worlds_eliminations_meta']['complete'] for player in verified), 713)
        busio = Player.objects.get(slug='busio')
        self.assertEqual(busio.career_stats['worlds']['games'], 33)
        self.assertEqual(busio.career_stats['career']['games'], 608)
        self.assertIn(2026, busio.attributes['worlds_playin'])
        self.assertIn(2026, Player.objects.get(slug='gury').attributes['worlds_eliminations']['play_in'])

    def test_upgrade_and_replay_preserve_ids_custom_metadata_answers_attempts_and_saved_scores(self):
        player = Player.objects.create(slug='busio', nickname='Old Busio',
            attributes={'leaguepedia_page': 'Busio', 'custom_note': {'keep': True}},
            career_stats={'custom_scope': {'games': 123}})
        extra = Player.objects.create(slug='custom-identity-outside-release', nickname='Custom')
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slot = DailySlot.objects.create(daily=daily, role='support', position=1)
        game = Submission.objects.create(daily=daily, guest_token='player-data-release-test',
                                         total_points=33.3, errors_used=2)
        answer = SubmissionAnswer.objects.create(submission=game, daily_slot=slot, player=player,
            is_correct=True, rarity_percent=33.3, points_awarded=-66.7, scoring_pick_count=1, scoring_sample_size=3)
        attempt = SubmissionAttempt.objects.create(submission=game, daily_slot=slot, player=player, is_correct=True)
        saved = (Submission.objects.get(pk=game.pk).__dict__.copy(),
                 SubmissionAnswer.objects.get(pk=answer.pk).__dict__.copy(),
                 SubmissionAttempt.objects.get(pk=attempt.pk).__dict__.copy())
        release.install_release(self.historical_apps, self.editor)
        current = Player.objects.get(pk=player.pk)
        self.assertEqual(current.slug, 'busio')
        self.assertEqual(current.attributes['custom_note'], {'keep': True})
        self.assertEqual(current.career_stats['custom_scope'], {'games': 123})
        self.assertTrue(Player.objects.filter(pk=extra.pk).exists())
        ids = dict(Player.objects.values_list('slug', 'pk'))
        with CaptureQueriesContext(connection) as queries:
            release.install_release(self.historical_apps, self.editor)
        self.assertFalse(any(row['sql'].lstrip().split()[0] in {'INSERT', 'UPDATE', 'DELETE'} for row in queries))
        self.assertEqual(dict(Player.objects.values_list('slug', 'pk')), ids)
        for model, pk, expected in [(Submission, game.pk, saved[0]), (SubmissionAnswer, answer.pk, saved[1]),
                                    (SubmissionAttempt, attempt.pk, saved[2])]:
            actual = model.objects.get(pk=pk).__dict__.copy()
            actual.pop('_state')
            expected.pop('_state')
            self.assertEqual(actual, expected)

    def test_invalid_current_release_fails_before_database_writes(self):
        document = {'schema_version': 1, 'release': release.RELEASE_NAME, 'players': deepcopy(release.load_release())}
        document['players'][0]['worlds_count'] = -1
        with self.assertNumQueries(0), self.assertRaisesRegex(ValueError, 'invalid Worlds counts'):
            release.validate_release(document)
