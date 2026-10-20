from copy import deepcopy
from datetime import date
import gzip,json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase,TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.dailies.models import Daily,DailySlot,DailySlotCondition
from apps.dailies.validators import evaluate_condition
from apps.submissions.models import Submission,SubmissionAnswer,SubmissionAttempt
from .activity import competitive_active,professional_event,year_before
from .models import Player
from .serializers import PlayerAutocompleteSerializer


def release_record(slug):
    data=json.loads(gzip.decompress((Path(__file__).parent/'fixtures/releases/worlds_players_2026_10_19_v1.json.gz').read_bytes()))
    return deepcopy(next(p for p in data['players'] if p['slug']==slug))


def bang_record():
    return release_record('bang')


class CompetitiveActivityTests(SimpleTestCase):
    def test_current_professional_players_remain_active(self):
        self.assertTrue(competitive_active(Player(**release_record('faker')),date(2026,10,21)))

    def test_bang_raw_active_flag_describes_streaming_not_professional_play(self):
        player=Player(**bang_record())
        self.assertTrue(player.is_active)
        self.assertFalse(competitive_active(player))
        self.assertTrue(evaluate_condition(player,'active','eq',False))
        self.assertFalse(evaluate_condition(player,'active','eq',True))
        self.assertTrue(evaluate_condition(player,'career_top5_champion','eq','Kalista'))
        self.assertFalse(PlayerAutocompleteSerializer(player).data['is_active'])

    @patch('apps.players.activity.activity_evidence')
    def test_rolling_year_uses_warsaw_dates_and_current_coaching_or_streaming_wins(self,evidence):
        player=SimpleNamespace(slug='person',attributes={'leaguepedia_page':'Person'},is_active=True)
        row={'leaguepedia_page':'Person','current_role':'Bot','retired':False,'covered_since':'2025-01-01',
             'last_professional_game':'2025-10-20T22:30:00+00:00'}
        evidence.return_value={'person':row}
        self.assertTrue(competitive_active(player,date(2026,10,21)))
        self.assertFalse(competitive_active(player,date(2026,10,22)))
        row['last_professional_game']='2026-10-20T12:00:00+00:00'
        for role in ('Coach','Streamer'):
            row['current_role']=role
            self.assertFalse(competitive_active(player,date(2026,10,21)))
        row['current_role']='Bot';row['last_professional_game']=None
        self.assertFalse(competitive_active(player,date(2026,10,21)))
        row['covered_since']='2026-01-01'
        self.assertIsNone(competitive_active(player,date(2026,10,21)))
        self.assertEqual(year_before(date(2024,2,29)),date(2023,2,28))

    def test_exhibitions_do_not_count_as_a_professional_return(self):
        for event in ['IDL Kings Lendas Season 4','Streamers Clash/Season 3','LPL All-Star 2026']:
            self.assertFalse(professional_event({'level':'Secondary','event':event}))
        self.assertTrue(professional_event({'level':'Secondary','event':'NLC/2026 Season/Spring Split'}))


class BangGuessRegressionTests(TestCase):
    def test_previous_wrong_guess_can_be_retried_and_other_saved_choices_stay_unchanged(self):
        player=Player.objects.create(**bang_record())
        daily=Daily.objects.create(date=timezone.localdate(),status='published')
        slot=DailySlot.objects.create(daily=daily,position=4,role='adc')
        for order,(kind,value) in enumerate([('active',False),('career_top5_champion','Kalista')]):
            DailySlotCondition.objects.create(slot=slot,condition_type=kind,value=value,order=order)
        game=Submission.objects.create(daily=daily,guest_token='bang-activity-regression',errors_used=1)
        SubmissionAnswer.objects.create(submission=game,daily_slot=slot,player=player,is_correct=False)
        old=SubmissionAttempt.objects.create(submission=game,daily_slot=slot,player=player,is_correct=False)
        old_values=SubmissionAttempt.objects.filter(pk=old.pk).values().get()
        other_slot=DailySlot.objects.create(daily=daily,position=1,role='mid')
        other=Player.objects.create(slug='saved-player',nickname='Saved player')
        saved=SubmissionAnswer.objects.create(submission=game,daily_slot=other_slot,player=other,is_correct=True,
            rarity_percent=12.5,points_awarded=-87.5,scoring_pick_count=1,scoring_sample_size=8)
        saved_values=SubmissionAnswer.objects.filter(pk=saved.pk).values().get()
        response=APIClient().post('/api/v1/submissions/answer/',{'daily_id':daily.pk,'slot_id':slot.pk,
            'player_slug':'bang','guest_token':game.guest_token},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue(response.data['is_correct'])
        self.assertEqual(response.data['errors_used'],1)
        self.assertEqual(SubmissionAttempt.objects.filter(pk=old.pk).values().get(),old_values)
        self.assertEqual(SubmissionAnswer.objects.filter(pk=saved.pk).values().get(),saved_values)
