from datetime import datetime,timedelta,timezone as dt_timezone
from unittest.mock import patch
from django.test import TestCase,SimpleTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.players.models import Player
from apps.players.test_activity import bang_record
from apps.users.models import GuestProfile
from apps.users.guest_profiles import guest_identity_key
from .models import InfinityRun,InfinityAttempt
from .infinity_rankings import bounds,snapshot,finished_result

NOW=datetime(2026,10,21,12,tzinfo=dt_timezone.utc)


class RankingCalendarTests(SimpleTestCase):
    def test_warsaw_day_and_week_include_the_autumn_clock_change(self):
        start,end=bounds('daily',datetime(2026,10,25,12,tzinfo=dt_timezone.utc))
        self.assertEqual((end.astimezone(dt_timezone.utc)-start.astimezone(dt_timezone.utc)).total_seconds(),25*3600)
        start,end=bounds('weekly',NOW)
        self.assertEqual((start.date().isoformat(),end.date().isoformat()),('2026-10-19','2026-10-26'))


class InfinityRankingTests(TestCase):
    def profile(self,name):
        return GuestProfile.objects.create(guest_key=guest_identity_key(name),nickname=name)

    def create_run(self,profile,score,stamp,finished=True):
        run=InfinityRun.objects.create(guest_profile=profile,display_suffix='public',correct_count=score,
            errors_used=10 if finished else 0,finished_at=stamp if finished else None)
        InfinityRun.objects.filter(pk=run.pk).update(updated_at=stamp,started_at=stamp)
        return run

    @patch('apps.submissions.infinity_rankings.timezone.now',return_value=NOW)
    def test_each_period_uses_its_own_best_run_and_one_row_per_person(self,_now):
        me=self.profile('period-player')
        for score,stamp in [(5,NOW),(10,datetime(2026,10,20,12,tzinfo=dt_timezone.utc)),
                            (20,datetime(2026,10,1,12,tzinfo=dt_timezone.utc)),
                            (30,datetime(2026,9,1,12,tzinfo=dt_timezone.utc))]:
            self.create_run(me,score,stamp)
        self.create_run(self.profile('opponent'),8,NOW)
        self.create_run(self.profile('zero-result'),0,NOW)
        self.create_run(self.profile('only-opened'),0,NOW,finished=False)
        expected={'daily':(5,2),'weekly':(10,1),'monthly':(20,1),'all_time':(30,1)}
        own=snapshot(me.pk,NOW)
        for period,(best,rank) in expected.items():
            response=APIClient().get('/api/v1/infinity/leaderboard/',{'period':period,'page_size':1,'page':rank})
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(response.data['period'],period)
            self.assertEqual(response.data['total_players'],3)
            self.assertEqual(response.data['results'][0]['correct_count'],best)
            self.assertEqual((own[period]['rank'],own[period]['best']),(rank,best))
        self.assertEqual(APIClient().get('/api/v1/infinity/leaderboard/',{'period':'invalid'}).status_code,400)

    @patch('apps.submissions.infinity_rankings.timezone.now',return_value=NOW)
    def test_midnight_is_warsaw_midnight(self,_now):
        self.create_run(self.profile('before-midnight'),10,datetime(2026,10,20,21,59,59,tzinfo=dt_timezone.utc))
        self.create_run(self.profile('after-midnight'),5,datetime(2026,10,20,22,tzinfo=dt_timezone.utc))
        data=APIClient().get('/api/v1/infinity/leaderboard/',{'period':'daily'}).data
        self.assertEqual(data['total_players'],1)
        self.assertEqual(data['results'][0]['correct_count'],5)

    @patch('apps.submissions.infinity_rankings.timezone.now',return_value=NOW)
    def test_second_run_persists_real_promotion_and_worse_runs_do_not_show_one(self,_now):
        token='promotion-guest-token'
        profile=self.profile(token)
        self.create_run(self.profile('first-rival'),10,NOW)
        self.create_run(self.profile('second-rival'),6,NOW)
        self.create_run(profile,3,NOW-timedelta(seconds=1))
        player=Player.objects.create(slug='wrong-mid',nickname='Wrong mid',primary_role='mid')
        board={'slots':[{'id':1,'position':1,'role':'top','conditions':[{'condition_type':'active','operator':'eq','value':True}],'candidate_ids':[]}]}
        client=APIClient()
        with patch('apps.submissions.infinity.make_board',return_value=board):
            start=client.post('/api/v1/infinity/start/',{'guest_token':token},format='json').data['run']
        InfinityRun.objects.filter(pk=start['id']).update(correct_count=8,errors_used=9)
        payload={'guest_token':token,'run_id':start['id'],'board_id':start['board_id'],'position':1,'player_slug':player.slug}
        result=client.post('/api/v1/infinity/answer/',payload,format='json')
        self.assertEqual(result.status_code,200,result.data)
        saved=result.data['run']['ranking_result']
        for row in saved['periods'].values():
            self.assertEqual((row['previous_rank'],row['rank'],row['improved']),(3,2,True))
        retry=client.post('/api/v1/infinity/answer/',payload,format='json')
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(retry.data['run']['ranking_result'],saved)
        self.assertEqual(client.post('/api/v1/infinity/state/',{'guest_token':token},format='json').data['run']['ranking_result'],saved)
        with patch('apps.submissions.infinity.make_board',return_value=board):
            second=client.post('/api/v1/infinity/start/',{'guest_token':token},format='json').data['run']
        InfinityRun.objects.filter(pk=second['id']).update(correct_count=1,errors_used=9)
        result=client.post('/api/v1/infinity/answer/',{**payload,'run_id':second['id'],'board_id':second['board_id']},format='json')
        self.assertTrue(all(not r['improved'] for r in result.data['run']['ranking_result']['periods'].values()))

    def test_existing_cached_board_accepts_bang_after_policy_correction(self):
        token='bang-infinity-regression'
        player=Player.objects.create(**bang_record())
        profile=self.profile(token)
        run=InfinityRun.objects.create(guest_profile=profile,display_suffix='test',errors_used=1,board={'slots':[
            {'id':4,'position':4,'role':'adc','candidate_ids':[],'conditions':[
                {'condition_type':'active','operator':'eq','value':False},
                {'condition_type':'career_top5_champion','operator':'eq','value':'Kalista'}]}]})
        old=InfinityAttempt.objects.create(run=run,board_id=run.board_id,position=4,player=player,is_correct=False)
        payload={'guest_token':token,'run_id':str(run.pk),'board_id':str(run.board_id),'position':4,'player_slug':player.slug}
        response=APIClient().post('/api/v1/infinity/answer/',payload,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertTrue(response.data['correct'])
        self.assertEqual(response.data['run']['correct_count'],1)
        self.assertEqual(response.data['run']['errors_used'],1)
        self.assertFalse(response.data['unchanged'])
        old.refresh_from_db()
        self.assertFalse(old.is_correct)
        self.assertEqual(InfinityAttempt.objects.filter(run=run).count(),2)
        retry=APIClient().post('/api/v1/infinity/answer/',payload,format='json')
        self.assertTrue(retry.data['unchanged'])
        self.assertEqual(retry.data['run']['correct_count'],1)
        self.assertEqual(InfinityAttempt.objects.filter(run=run).count(),2)

    def test_new_day_does_not_compare_places_from_two_different_daily_rankings(self):
        profile=self.profile('midnight-promotions')
        yesterday=NOW-timedelta(days=1)
        self.create_run(profile,3,yesterday)
        self.create_run(self.profile('midnight-rival'),6,yesterday)
        before={'completed_runs':1,'ranks':snapshot(profile.pk,yesterday)}
        run=self.create_run(profile,8,NOW)
        run.ranking_before=before
        result=finished_result(run)['periods']
        self.assertIsNone(result['daily']['previous_rank'])
        self.assertFalse(result['daily']['improved'])
        self.assertTrue(result['weekly']['improved'])
