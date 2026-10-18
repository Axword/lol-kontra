import gzip
import json
from pathlib import Path

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.dailies.validators import PlayerFacts
from apps.players.models import Player

from .models import Submission, SubmissionAttempt


class CareerReleaseGameplayTests(TestCase):
    def test_knight_release_record_matches_orianna_career_top_five_through_api(self):
        release = (Path(__file__).resolve().parents[1] / 'players' / 'fixtures' / 'releases'
                   / 'worlds_players_2026_10_18_v1.json.gz')
        records = json.loads(gzip.decompress(release.read_bytes()))['players']
        record = next(record for record in records if record['slug'] == 'knight-zhuo-ding')
        knight = Player.objects.create(**record)
        career = knight.career_stats['career']
        self.assertEqual(career['champions'][0], {'champion': 'Orianna', 'games': 91, 'wins': 58})
        self.assertEqual(PlayerFacts(knight).career_top5_champions,
                         ['Orianna', 'Ahri', 'Syndra', 'Taliyah', 'Ryze'])

        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        for position, role in enumerate(['top', 'jungle', 'mid', 'adc', 'support'], 1):
            slot = DailySlot.objects.create(daily=daily, position=position, role=role)
            DailySlotCondition.objects.create(
                slot=slot, condition_type='residency', value='LPL', order=0,
                label_pl='Region: LPL', label_en='Region: LPL',
            )
            condition, value = ('career_top5_champion', 'Orianna') if role == 'mid' else ('country', 'CN')
            DailySlotCondition.objects.create(
                slot=slot, condition_type=condition, value=value, order=1,
                label_pl='Orianna w TOP 5 kariery' if role == 'mid' else 'Chiny',
                label_en='Orianna in career top 5' if role == 'mid' else 'China',
            )
        mid = daily.slots.get(role='mid')

        response = APIClient().post('/api/v1/submissions/answer/', {
            'daily_id': daily.pk, 'slot_id': mid.pk, 'player_slug': knight.slug,
            'guest_token': 'knight-career-release-regression',
        }, format='json')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data['is_correct'])
        self.assertEqual(response.data['player_slug'], knight.slug)
        self.assertEqual(response.data['correct_count'], 1)
        self.assertEqual(response.data['errors_used'], 0)
        submission = Submission.objects.get(pk=response.data['submission_id'])
        self.assertEqual(submission.errors_used, 0)
        self.assertTrue(submission.answers.get(daily_slot=mid).is_correct)
        self.assertTrue(SubmissionAttempt.objects.get(submission=submission).is_correct)
