"""
Import historical team data and player-team history from JSON fixture.

Usage:
    python manage.py import_team_history
    python manage.py import_team_history --from-json path/to/teams.json
    python manage.py import_team_history --dry-run
"""
import json
import os
from django.core.management.base import BaseCommand
from apps.players.models import Player, Team, PlayerTeamHistory


# Domyślna ścieżka do fixture
DEFAULT_TEAMS_JSON = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '..', '..',
    'scraper', 'data', 'worlds_teams.json'
)


class Command(BaseCommand):
    help = 'Import team history and player-team assignments from JSON'

    def add_arguments(self, parser):
        parser.add_argument('--from-json', type=str, help='Path to teams JSON file')
        parser.add_argument('--dry-run', action='store_true', help='Show what would be imported')
        parser.add_argument('--teams-only', action='store_true', help='Only import teams, skip player history')

    def handle(self, *args, **options):
        path = options.get('from_json') or DEFAULT_TEAMS_JSON
        if not os.path.exists(path):
            self.stderr.write(f"File not found: {path}")
            self.stderr.write("Run: python manage.py import_team_history --from-json <path>")
            return

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        teams_data = data.get('teams', [])
        history_data = data.get('player_team_history', [])

        # 1. Import teams
        created_teams, updated_teams = 0, 0
        for team in teams_data:
            slug = team.get('slug', '').lower().replace(' ', '-')
            if not slug:
                continue

            defaults = {
                'name': team.get('name', slug),
                'region': team.get('region', ''),
                'country_code': team.get('country_code', ''),
                'is_active': team.get('is_active', True),
                'is_worlds_champion': team.get('is_worlds_champion', False),
                'worlds_titles_years': team.get('worlds_titles_years', []),
                'logo_url': team.get('logo_url', ''),
            }

            if not options['dry_run']:
                _, created = Team.objects.update_or_create(slug=slug, defaults=defaults)
                if created:
                    created_teams += 1
                else:
                    updated_teams += 1

        self.stdout.write(
            f"Teams: {created_teams} created, {updated_teams} updated"
            + (' [dry-run]' if options['dry_run'] else '')
        )

        if options.get('teams_only'):
            return

        # 2. Import player-team history
        created_history = 0
        skipped = 0

        for entry in history_data:
            player_slug = entry.get('player_slug', '')
            team_slug = entry.get('team_slug', '')

            if not player_slug or not team_slug:
                skipped += 1
                continue

            try:
                player = Player.objects.get(slug=player_slug)
            except Player.DoesNotExist:
                skipped += 1
                continue

            try:
                team = Team.objects.get(slug=team_slug)
            except Team.DoesNotExist:
                # Auto-create team if not found
                team = Team.objects.create(
                    slug=team_slug,
                    name=team_slug.replace('-', ' ').title(),
                    region=entry.get('region', ''),
                )

            defaults = {
                'start_date': entry.get('start_date'),
                'end_date': entry.get('end_date'),
                'role': entry.get('role', ''),
            }

            if not options['dry_run']:
                _, created = PlayerTeamHistory.objects.update_or_create(
                    player=player, team=team,
                    start_date=defaults['start_date'],
                    defaults={'end_date': defaults['end_date'], 'role': defaults['role']},
                )
                if created:
                    created_history += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Player-Team History: {created_history} created, {skipped} skipped"
                + (' [dry-run]' if options['dry_run'] else '')
            )
        )
