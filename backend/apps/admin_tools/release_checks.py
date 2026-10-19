"""Read-only checks for the offline data shipped with this release."""
from importlib import import_module
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from apps.dailies.models import Daily
from apps.dailies.validators import PlayerFacts
from apps.players.models import Player
from apps.players.career_roles import with_verified_career_roles
from apps.submissions.models import Submission


def check_release_data(*, database='default', strict=False):
    executor = MigrationExecutor(connections[database])
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise ValueError('Database has pending migrations; run migrate first')
    source = import_module('apps.players.migrations.0005_worlds_2026_october_19_release')
    calendar_source = import_module('apps.dailies.migrations._october_2026_release')
    records, calendar = source.load_release(), calendar_source.load_calendar()
    players = Player.objects.using(database).in_bulk([row['slug'] for row in records], field_name='slug')
    if len(players) != len(records):
        raise ValueError('Player release is incomplete: expected 882 identities')
    verified = photos = careers = 0
    for row in records:
        row = with_verified_career_roles(row)
        player = players[row['slug']]
        if row['attributes'].get('worlds_verified') is True:
            facts = PlayerFacts(player)
            if (player.attributes.get('worlds_verified') is not True or not facts.worlds_stats
                    or not facts.worlds_champions or not isinstance(player.attributes.get('leagues_meta'), dict)
                    or player.attributes['leagues_meta'].get('source') != 'Leaguepedia'):
                raise ValueError(f'Incomplete verified player data: {player.slug}')
            verified += 1
            photos += player.attributes.get('portrait_status') == 'available'
            careers += facts.career_stats is not None
        if strict and (any(getattr(player, key) != row[key] for key in source.SCALAR_FIELDS)
                or any(player.attributes.get(key) != value for key, value in row['attributes'].items())
                or any(player.career_stats.get(key) != value for key, value in row['career_stats'].items())):
            raise ValueError(f'Fresh player data differs from release: {player.slug}')
    dates = [row['date'] for row in calendar]
    dailies = list(Daily.objects.using(database).filter(date__in=dates).prefetch_related('slots__conditions'))
    if len(dailies) != 31:
        raise ValueError('October calendar is incomplete: expected all 31 dates')
    for daily in dailies:
        slots = list(daily.slots.all())
        if ([(slot.position, slot.role) for slot in slots] != list(enumerate(calendar_source.ROLES, 1))
                or any(len(slot.conditions.all()) != 2 for slot in slots)):
            raise ValueError(f'Calendar board {daily.date} needs five roles and two requirements each')
    seeds = Submission.objects.using(database).filter(is_seed=True)
    if seeds.exists():
        raise ValueError('Synthetic test rosters are retired; run all migrations before publishing')
    return {'players': len(players), 'verified': verified, 'photos': photos, 'career_stats': careers,
            'boards': len(dailies), 'test_rosters': seeds.count()}
