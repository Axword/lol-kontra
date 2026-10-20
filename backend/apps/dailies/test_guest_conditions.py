from datetime import date
from importlib import import_module
import random
from types import SimpleNamespace
import unittest

from django.apps import apps
from django.db import connection
from django.test import TestCase

from apps.players.models import Player
from apps.submissions.models import Submission, SubmissionAnswer
from .career_regions import career_regions
from .community import _author
from .generator import generate_slot, count_candidates, validate_daily, HARD
from .models import Daily, DailySlot, DailySlotCondition
from .tests_validators import FakePlayer
from .validators import evaluate_condition

release = import_module('apps.dailies.migrations._guest_board_2026')


class GuestConditionTests(unittest.TestCase):
    def matches(self, kind, value=True, attributes=None, **kwargs):
        return evaluate_condition(FakePlayer(attributes=attributes or {}, **kwargs), kind, 'eq', value)

    def test_group_exit_is_any_main_event_group_elimination_strictly_before_cutoff(self):
        for history, expected in [({'group': [2019, 2021]}, True), ({'group': [2020]}, False),
                                  ({'play_in': [2019]}, False), ({'group': []}, False),
                                  ({'group': ['2019']}, False)]:
            self.assertEqual(self.matches('worlds_group_exit_before', 2020,
                                          {'worlds_eliminations': history}), expected)
        self.assertFalse(self.matches('worlds_group_exit_before', 2020))

    def test_playin_participation_does_not_require_advancement(self):
        facts = {'worlds_playin_appearances': [2018], 'worlds_playin': []}
        self.assertTrue(self.matches('worlds_playin_appearance', attributes=facts))
        self.assertFalse(self.matches('worlds_playin', attributes=facts))
        self.assertFalse(self.matches('worlds_playin_appearance'))

    def test_unknown_nationality_does_not_prove_non_korean(self):
        self.assertFalse(self.matches('country_excluded', 'KR', country_code=''))
        self.assertFalse(self.matches('country_excluded', 'KR', country_code='KR'))
        self.assertTrue(self.matches('country_excluded', 'KR', country_code='TW'))

    def test_titles_exact_and_debut_use_actual_appearances(self):
        facts = {'worlds_titles_verified': True, 'worlds_titles': [2014],
                 'worlds_appearances': [2013, 2014]}
        self.assertTrue(self.matches('worlds_titles_exact', 1, facts))
        self.assertFalse(self.matches('worlds_title_on_debut', attributes=facts))
        facts['worlds_appearances'] = [2014]
        self.assertTrue(self.matches('worlds_title_on_debut', attributes=facts))
        facts['worlds_titles'] = [2014, 2017]
        self.assertFalse(self.matches('worlds_titles_exact', 1, facts))
        self.assertFalse(self.matches('worlds_titles_exact', 0))

    def test_lost_to_faker_excludes_champions_and_other_finals(self):
        for finals, titles, expected in [([2023], [], True), ([2023], [2023], False),
                                        ([2019], [], False), ([2022], [], False), ([2016], [], True)]:
            self.assertEqual(self.matches('worlds_final_lost_to_faker', attributes={
                'worlds_finals': finals, 'worlds_titles': titles}), expected)
        self.assertFalse(self.matches('worlds_final_lost_to_faker'))

    def test_domestic_regions_ignore_renames_international_events_and_residency(self):
        meta = {'source': 'Leaguepedia', 'scope': 'leaguepedia_dated_league_appearances',
                'complete': True, 'league_groups': [
                    {'league': 'Europe League Championship Series', 'games': 10},
                    {'league': 'LoL EMEA Championship', 'games': 10},
                    {'league': 'Esports World Cup', 'games': 10},
                ]}
        self.assertEqual(career_regions({'leagues_meta': meta}), {'EU'})
        meta['league_groups'].append({'league': 'League of Legends Championship of The Americas South', 'games': 5})
        self.assertEqual(career_regions({'leagues_meta': meta}), {'EU', 'BR'})
        meta['complete'] = False
        self.assertEqual(career_regions({'leagues_meta': meta}), set())
        self.assertEqual(career_regions({'leagues': ['LEC', 'LCS']}), set())

    def test_masters_and_penta_require_positive_source_evidence(self):
        facts = {'european_masters': {'source': 'Leaguepedia', 'played': ['European Masters/2020/Summer'], 'titles': []},
                 'additional_worlds_facts': {'source': 'Leaguepedia', 'pentakills': 1}}
        self.assertTrue(self.matches('european_masters_played', attributes=facts))
        self.assertFalse(self.matches('european_masters_won', attributes=facts))
        self.assertTrue(evaluate_condition(FakePlayer(attributes=facts), 'pentakill_worlds', 'gte', 1))
        self.assertFalse(self.matches('european_masters_played'))


class GuestReleaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed_players', full=True, verbosity=0)

    def install(self):
        release.install(apps, SimpleNamespace(connection=connection))
        return Daily.objects.get(date=date(2026, 10, 22))

    def test_exact_guest_board_is_solvable_and_reinstallation_preserves_ids(self):
        daily = self.install()
        self.assertEqual(validate_daily(daily), daily)
        slots = list(daily.slots.order_by('position').prefetch_related('conditions'))
        self.assertEqual([s.role for s in slots], ['top', 'jungle', 'mid', 'adc', 'support'])
        self.assertEqual([s.conditions.count() for s in slots], [2, 2, 1, 2, 2])
        pools = {s.role: {p.nickname.casefold() for p in count_candidates(s)} for s in slots}
        for role, positive, negative in [('top', 'hanabi', 'zeus'), ('jungle', 'jankos', 'canyon'),
                                          ('mid', 'bjergsen', 'faker'), ('adc', 'celebrity', 'uzi'),
                                          ('support', 'trymbi', 'keria')]:
            self.assertIn(positive, pools[role])
            self.assertNotIn(negative, pools[role])
        ids = list(DailySlotCondition.objects.filter(slot__daily=daily).values_list('pk', flat=True))
        self.install()
        self.assertEqual(list(DailySlotCondition.objects.filter(slot__daily=daily).values_list('pk', flat=True)), ids)
        self.assertEqual(_author(daily)['avatar_url'], '/authors/kaczy.png')

    def test_migration_never_rewrites_a_started_board_or_saved_score(self):
        daily = Daily.objects.create(date=date(2026, 10, 22), author_name='Existing')
        slot = DailySlot.objects.create(daily=daily, role='mid', position=1)
        condition = DailySlotCondition.objects.create(slot=slot, condition_type='country', value='KR')
        submission = Submission.objects.create(daily=daily, guest_token='real-person', total_points=405)
        answer = SubmissionAnswer.objects.create(submission=submission, daily_slot=slot,
            player=Player.objects.get(slug='faker'), is_correct=True, rarity_percent=5, points_awarded=-95)
        before = (list(Daily.objects.filter(pk=daily.pk).values()), list(DailySlotCondition.objects.filter(pk=condition.pk).values()),
                  list(Submission.objects.filter(pk=submission.pk).values()), list(SubmissionAnswer.objects.filter(pk=answer.pk).values()))
        self.install()
        after = (list(Daily.objects.filter(pk=daily.pk).values()), list(DailySlotCondition.objects.filter(pk=condition.pk).values()),
                 list(Submission.objects.filter(pk=submission.pk).values()), list(SubmissionAnswer.objects.filter(pk=answer.pk).values()))
        self.assertEqual(before, after)

    def test_upcoming_calendar_has_varied_playable_boards_and_keeps_kaczy(self):
        upcoming = import_module('apps.dailies.migrations._upcoming_october_2026')
        guest = self.install()
        guest_ids = list(guest.slots.values_list('conditions__pk', flat=True))
        upcoming.install(apps, SimpleNamespace(connection=connection), today=date(2026, 10, 20))
        boards = Daily.objects.exclude(pk=guest.pk).order_by('date')
        # This frozen release predates the ten-answer policy.
        boards.update(minimum_candidates=None)
        self.assertEqual(boards.count(), 10)
        self.assertEqual(list(guest.slots.values_list('conditions__pk', flat=True)), guest_ids)
        before = list(DailySlotCondition.objects.order_by('pk').values())
        upcoming.install(apps, SimpleNamespace(connection=connection), today=date(2026, 10, 20))
        self.assertEqual(list(DailySlotCondition.objects.order_by('pk').values()), before)
        # Current role validation applies after the subsequent editorial release.
        import_module('apps.dailies.migrations.0020_worlds_focused_future_boards').install(
            apps, SimpleNamespace(connection=connection))
        for board in boards:
            validate_daily(board)
            self.assertFalse(DailySlotCondition.objects.filter(slot__daily=board, condition_type='birth_year_range').exists())

    def test_upcoming_calendar_skips_past_today_and_started_games(self):
        upcoming = import_module('apps.dailies.migrations._upcoming_october_2026')
        self.install()
        past = Daily.objects.create(date=date(2026, 10, 21), author_name='Past')
        started = Daily.objects.create(date=date(2026, 10, 26), author_name='Started')
        old = DailySlot.objects.create(daily=started, role='mid', position=1)
        clue = DailySlotCondition.objects.create(slot=old, condition_type='country', value='KR')
        game = Submission.objects.create(daily=started, guest_token='keep-upcoming-game', total_points=123)
        before = (list(Daily.objects.filter(pk__in=[past.pk, started.pk]).values()),
                  list(Submission.objects.filter(pk=game.pk).values()))
        upcoming.install(apps, SimpleNamespace(connection=connection), today=date(2026, 10, 25))
        self.assertEqual(before, (list(Daily.objects.filter(pk__in=[past.pk, started.pk]).values()),
                                  list(Submission.objects.filter(pk=game.pk).values())))
        self.assertTrue(DailySlotCondition.objects.filter(pk=clue.pk).exists())
        self.assertFalse(Daily.objects.filter(date=date(2026, 10, 25)).exists())

    def test_single_rare_clue_is_allowed_but_a_broad_clue_is_rejected(self):
        daily = Daily.objects.create(date=date(2026, 12, 1))
        pool = [Player.objects.create(slug=f'rare-{n}', nickname=f'Rare {n}', primary_role='mid',
                                     attributes={'worlds_finals': [2018] if n < 10 else []}) for n in range(60)]
        clue = [('final', HARD, 'worlds_final', 'eq', True, 'Finalista Worlds', 'Worlds finalist')]
        slot, candidates = generate_slot(daily, 'mid', 1, HARD, random.Random(2), set(), pool, clue)
        self.assertEqual(slot.conditions.count(), 1)
        self.assertEqual(len(candidates), 10)
        broad = [('origin', HARD, 'country', 'eq', 'KR', 'Koreańczyk', 'Korean')]
        with self.assertRaises(ValueError):
            generate_slot(daily, 'mid', 2, HARD, random.Random(2), set(), pool, broad)
