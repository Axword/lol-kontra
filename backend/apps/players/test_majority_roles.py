from copy import deepcopy
from importlib import import_module
from types import SimpleNamespace
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from apps.dailies.models import Daily, DailySlot, DailySlotCondition
from apps.dailies.validators import PlayerFacts, player_matches_slot
from apps.players.models import Player
from apps.players.career_roles import with_verified_career_roles
from apps.players.majority_roles import role_evidence
from apps.submissions.models import Submission, SubmissionAnswer


class MajorityRoleEvidenceTests(SimpleTestCase):
    def player(self, slug):
        source = import_module('apps.players.migrations.0005_worlds_2026_october_19_release')
        row = with_verified_career_roles(deepcopy(next(p for p in source.load_release() if p['slug'] == slug)))
        return SimpleNamespace(**row)

    def test_official_majorities_keep_real_swaps_and_reject_one_map_roles(self):
        self.assertEqual(PlayerFacts(self.player('kikis')).roles, {'top', 'jungle'})
        self.assertEqual(PlayerFacts(self.player('yellowstar')).roles, {'support', 'adc'})
        self.assertEqual(PlayerFacts(self.player('perkz')).roles, {'mid', 'adc'})
        self.assertEqual(PlayerFacts(self.player('ambition')).roles, {'mid', 'jungle'})
        self.assertEqual(PlayerFacts(self.player('faker')).roles, {'mid'})
        # Rekkles has a source-backed majority as support in LEC Versus 2026.
        self.assertEqual(PlayerFacts(self.player('rekkles')).roles, {'adc', 'support'})
        # A metadata label alone still cannot establish a later role swap.
        changed_metadata = self.player('faker')
        changed_metadata.primary_role = 'support'
        changed_metadata.secondary_roles = ['mid']
        self.assertEqual(PlayerFacts(changed_metadata).roles, {'mid'})

    def test_worlds_condition_does_not_count_a_domestic_only_swap(self):
        self.assertEqual(PlayerFacts(self.player('kikis')).worlds_roles, {'jungle'})
        self.assertEqual(PlayerFacts(self.player('perkz')).worlds_roles, {'mid', 'adc'})

    def test_every_accepted_role_is_more_than_half_of_the_team_event_maps(self):
        for row in role_evidence().values():
            for evidence in row['evidence']:
                self.assertGreater(evidence['games'] * 2, evidence['team_games'])
                self.assertIn(evidence['scope'], ['worlds', 'major_league'])


class ArchivedRoleGuessTests(TestCase):
    def test_saved_off_role_answer_is_retained_but_a_new_guess_is_rejected(self):
        player = Player.objects.create(slug='faker', nickname='Faker', primary_role='mid', secondary_roles=['top'],
            attributes={'worlds_verified': True, 'leaguepedia_page': 'Faker'})
        daily = Daily.objects.create(date=timezone.localdate(), status='published')
        slot = DailySlot.objects.create(daily=daily, position=1, role='top')
        DailySlotCondition.objects.create(slot=slot, condition_type='active', operator='eq', value=True)
        old = Submission.objects.create(daily=daily, guest_token='previous-player-token')
        saved = SubmissionAnswer.objects.create(submission=old, daily_slot=slot, player=player, is_correct=True)
        self.assertFalse(player_matches_slot(player, slot))
        client = APIClient()
        response = client.post('/api/v1/submissions/answer/', {'daily_id':daily.pk, 'slot_id':slot.pk,
            'player_slug':player.slug, 'guest_token':'new-player-token-1234'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['is_correct'])
        saved.refresh_from_db()
        self.assertTrue(saved.is_correct)
        previous = client.get('/api/v1/submissions/me/', {'daily_id':daily.pk, 'guest_token':'previous-player-token'})
        self.assertTrue(previous.data['answers'][0]['is_correct'])
