from copy import deepcopy
from unittest.mock import patch
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.players.models import Player
from apps.users.models import GuestProfile
from apps.users.guest_profiles import guest_identity_key
from .models import InfinityAttempt, InfinityRun, Submission


class InfinityTests(TestCase):
    token = 'infinity-player-token-1234'
    def setUp(self):
        self.client = APIClient()
        self.players = [Player.objects.create(slug=f'answer-{index}', nickname=f'Answer {index}',
            primary_role=role) for index,role in enumerate(['top','jungle','mid','adc','support'])]
        self.wrong = [Player.objects.create(slug=f'wrong-{index}', nickname=f'Wrong {index}') for index in range(10)]
        self.board = {'signature':[], 'theme_year':2020, 'slots':[
            {'id':i+1, 'position':i+1, 'role':p.primary_role, 'label_pl':p.primary_role,'label_en':p.primary_role,
             'conditions':[{'id':i,'condition_type':'active','operator':'eq','value':True,'label_pl':'Aktywny','label_en':'Active'}],
             'candidate_ids':[p.pk]} for i,p in enumerate(self.players)]}
        patcher = patch('apps.submissions.infinity.make_board', side_effect=lambda previous=None:deepcopy(self.board))
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, endpoint, **data):
        return self.client.post('/api/v1/infinity/'+endpoint+'/', {'guest_token':self.token,**data}, format='json')

    def start(self):
        response = self.post('start')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn(b'candidate_ids', response.content)
        self.assertNotIn(guest_identity_key(self.token).encode(), response.content)
        return response.data['run']

    def answer(self, run, player, position=1, **extra):
        return self.post('answer', run_id=run['id'], board_id=run['board_id'],position=position,player_slug=player.slug,**extra)

    def test_opening_state_is_read_only_and_start_is_idempotent(self):
        self.assertIsNone(self.post('state').data['run'])
        self.assertEqual(InfinityRun.objects.count(),0)
        first=self.start()
        self.assertEqual(self.start()['id'],first['id'])
        self.assertEqual(InfinityRun.objects.count(),1)
        self.assertEqual(Submission.objects.count(),0)

    def test_ten_errors_are_shared_across_new_boards_and_server_counts_correct_guesses(self):
        run=self.start()
        for player in self.wrong[:9]:
            result=self.answer(run,player)
            self.assertEqual(result.status_code,200)
        for position,player in enumerate(self.players,1):
            result=self.answer(run,player,position,correct_count=999999,errors_left=1000)
            self.assertTrue(result.data['correct'])
        next_board=result.data['run']
        self.assertNotEqual(next_board['board_id'],run['board_id'])
        self.assertEqual(next_board['correct_count'],5)
        self.assertEqual(next_board['errors_left'],1)
        self.assertEqual(next_board['answers'],[])
        final=self.answer(next_board,self.wrong[-1]).data['run']
        self.assertTrue(final['is_over'])
        self.assertEqual(final['errors_left'],0)
        blocked=self.answer(final,self.players[0])
        self.assertEqual(blocked.status_code,409)
        self.assertEqual(InfinityRun.objects.get(pk=run['id']).correct_count,5)
        restarted=self.start()
        self.assertNotEqual(restarted['id'],run['id'])
        self.assertEqual((restarted['correct_count'],restarted['errors_left']),(0,10))
        self.assertEqual(self.post('state').data['personal_best'],5)
        self.assertEqual(Submission.objects.count(),0)

    def test_repeated_requests_do_not_cost_another_life_or_award_another_hit(self):
        run=self.start()
        self.answer(run,self.wrong[0])
        repeated=self.answer(run,self.wrong[0])
        self.assertTrue(repeated.data['unchanged'])
        self.assertEqual(repeated.data['run']['errors_used'],1)
        self.answer(run,self.players[0])
        repeated=self.answer(run,self.players[0])
        self.assertTrue(repeated.data['unchanged'])
        self.assertEqual(repeated.data['run']['correct_count'],1)
        for position,player in enumerate(self.players[1:],2):
            self.answer(run,player,position)
        old_retry=self.answer(run,self.players[-1],5)
        self.assertTrue(old_retry.data['unchanged'])
        self.assertEqual(old_retry.data['run']['correct_count'],5)
        self.assertEqual(old_retry.data['run']['errors_used'],1)
        self.assertEqual(InfinityAttempt.objects.filter(is_correct=True).count(),5)

    def test_another_guest_cannot_read_or_change_a_run_and_stale_boards_do_not_cost_lives(self):
        run=self.start()
        response=self.client.post('/api/v1/infinity/answer/', {'guest_token':'another-guest-token',
            'run_id':run['id'],'board_id':run['board_id'],'position':1,'player_slug':self.players[0].slug},format='json')
        self.assertEqual(response.status_code,404)
        self.assertIsNone(self.client.post('/api/v1/infinity/state/',{'guest_token':'another-guest-token'},format='json').data['run'])
        for position,player in enumerate(self.players,1):
            self.answer(run,player,position)
        stale=self.answer(run,self.wrong[0])
        self.assertEqual(stale.status_code,409)
        self.assertEqual(stale.data['run']['errors_used'],0)

    def test_ranking_uses_each_persons_best_run_and_paginates_without_identity_secrets(self):
        self.start()
        profile=GuestProfile.objects.get(guest_key=guest_identity_key(self.token))
        InfinityRun.objects.filter(guest_profile=profile).update(correct_count=5)
        InfinityRun.objects.create(guest_profile=profile,display_suffix='old',correct_count=3,errors_used=10,finished_at=timezone.now())
        other=GuestProfile.objects.create(guest_key=guest_identity_key('ranking-other-guest'),nickname='Worlds fan')
        InfinityRun.objects.create(guest_profile=other,display_suffix='suffix',correct_count=8)
        first=self.client.get('/api/v1/infinity/leaderboard/',{'page_size':1})
        second=self.client.get('/api/v1/infinity/leaderboard/',{'page_size':1,'page':2})
        self.assertEqual(first.data['total_players'],2)
        self.assertEqual(first.data['total_pages'],2)
        self.assertEqual(first.data['results'][0]['correct_count'],8)
        self.assertEqual(second.data['results'][0]['correct_count'],5)
        self.assertNotIn(self.token.encode(),first.content+second.content)
        self.assertNotIn(profile.guest_key.encode(),first.content+second.content)
        self.assertNotIn('id',first.data['results'][0])

    def test_database_rejects_extra_active_runs_and_impossible_error_totals(self):
        run=self.start()
        profile=InfinityRun.objects.get(pk=run['id']).guest_profile
        with self.assertRaises(IntegrityError),transaction.atomic():
            InfinityRun.objects.create(guest_profile=profile,display_suffix='duplicate')
        with self.assertRaises(IntegrityError),transaction.atomic():
            InfinityRun.objects.filter(pk=run['id']).update(errors_used=11)


class InfinityConcurrencyTests(TransactionTestCase):
    def test_simultaneous_retries_award_exactly_one_correct_guess(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import connections, close_old_connections
        token='concurrent-infinity-guest'
        player=Player.objects.create(slug='concurrent-player',nickname='Player')
        profile=GuestProfile.objects.create(guest_key=guest_identity_key(token))
        run=InfinityRun.objects.create(guest_profile=profile,display_suffix='concurrent',board={
            'slots':[{'id':1,'position':1,'role':'mid','conditions':[{'condition_type':'active','operator':'eq','value':True}],'candidate_ids':[player.pk]}]})
        data={'guest_token':token,'run_id':str(run.pk),'board_id':str(run.board_id),'position':1,'player_slug':player.slug}
        def submit(_):
            close_old_connections()
            try:
                response=APIClient().post('/api/v1/infinity/answer/',data,format='json')
                return response.status_code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(list(executor.map(submit,range(2))),[200,200])
        run.refresh_from_db()
        self.assertEqual(run.correct_count,1)
        self.assertEqual(InfinityAttempt.objects.count(),1)
