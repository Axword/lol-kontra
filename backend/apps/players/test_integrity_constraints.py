from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Coach, Player, PlayerCoachHistory, PlayerTeamHistory, Team, TournamentAppearance


class PlayerIntegrityConstraintTests(TestCase):
    def test_direct_sql_updates_cannot_write_invalid_counts_roles_or_json(self):
        player = Player.objects.create(slug='person', nickname='Person')
        invalid = ({'worlds_count': -1}, {'worlds_titles_count': -1}, {'primary_role': 'coach'},
                   {'secondary_roles': ['invalid']}, {'birth_year': 999},
                   {'attributes': []}, {'career_stats': ['not an object']})
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(IntegrityError), transaction.atomic():
                Player.objects.filter(pk=player.pk).update(**values)
        player.refresh_from_db()
        self.assertEqual((player.worlds_count, player.primary_role, player.attributes), (0, 'mid', {}))

    def test_history_dates_placements_and_years_are_guarded(self):
        player = Player.objects.create(slug='person', nickname='Person')
        team = Team.objects.create(slug='team', name='Team')
        coach = Coach.objects.create(slug='coach', name='Coach')
        factories = (
            lambda: PlayerTeamHistory.objects.create(player=player, team=team, start_date=date(2020, 1, 2), end_date=date(2020, 1, 1)),
            lambda: PlayerTeamHistory.objects.create(player=player, team=team, role='coach'),
            lambda: TournamentAppearance.objects.create(player=player, tournament_slug='a', year=2020, placement=0),
            lambda: TournamentAppearance.objects.create(player=player, tournament_slug='b', year=0),
            lambda: TournamentAppearance.objects.create(player=player, tournament_slug='c', year=2020, role='coach'),
            lambda: PlayerCoachHistory.objects.create(player=player, coach=coach, year=-1),
        )
        for factory in factories:
            with self.assertRaises(IntegrityError), transaction.atomic():
                factory()
        PlayerTeamHistory.objects.create(player=player, team=team, start_date=None, end_date=None, role='')
        TournamentAppearance.objects.create(player=player, tournament_slug='valid', year=2020, placement=None)
        PlayerCoachHistory.objects.create(player=player, coach=coach, year=None)
