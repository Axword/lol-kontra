"""Explicit, previewable correction of the unstarted 20 October board."""
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.dailies.generator import ROLE_ORDER, count_candidates, validate_daily
from apps.dailies.models import Daily, DailySlotCondition


BOARD = [
    [('worlds_top5_champion', 'eq', 'Olaf', 'Olaf w jego TOP 5 według liczby gier na Worlds', 'Olaf in his top 5 champions by games played at Worlds')],
    [('worlds_title_on_debut', 'eq', True, 'Wygrał Worlds będąc debiutantem turnieju', 'Won Worlds on his first appearance at the tournament')],
    [('european_masters_won', 'eq', True, 'Wygrał EU Masters / EMEA Masters', 'Won EU / EMEA Masters')],
    [('active', 'eq', False, 'Zakończył karierę', 'Retired'),
     ('career_top5_champion', 'eq', 'Kalista', 'Kalista w jego TOP 5 według liczby gier w karierze', 'Kalista in his top 5 champions by games played in his career')],
    [('worlds_final_lost_to_faker', 'eq', True, 'Przegrał finał Worlds przeciwko Fakerowi', 'Lost a Worlds final to Faker')],
]
ORIGINAL = [
    [('worlds_top5_champion', 'eq', 'Olaf'), ('worlds_games', 'lt', 100)],
    [('residency', 'eq', 'LCK'), ('birth_year_range', 'eq', {'min': 1990, 'max': 1999})],
    [('worlds_group_escape', 'eq', True), ('birth_year_range', 'eq', {'min': 1990, 'max': 1999})],
    [('active', 'eq', False), ('career_top5_champion', 'eq', 'Kalista')],
    [('worlds_win_rate', 'gt', 50), ('birth_year_range', 'eq', {'min': 1990, 'max': 1999})],
]


class Command(BaseCommand):
    help = 'Preview the curated 2026-10-20 board; --apply updates it only before any games exist.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        daily = Daily.objects.select_for_update().get(date=date(2026, 10, 20))
        slots = list(daily.slots.select_for_update().order_by('position'))
        if [s.role for s in slots] != ROLE_ORDER:
            raise CommandError('Unexpected slots; no changes made.')
        actual = [list(s.conditions.order_by('order', 'pk').values_list('condition_type', 'operator', 'value')) for s in slots]
        target = [[c[:3] for c in row] for row in BOARD]
        if actual == target:
            self.stdout.write('The curated board is already installed.')
            return
        if actual != ORIGINAL:
            raise CommandError('The board differs from the reviewed original; no changes made.')
        # The daily row lock also blocks new submissions through their FK.
        if daily.submissions.exists():
            raise CommandError('Games already exist; their conditions were preserved.')
        for slot, clues, previous in zip(slots, BOARD, actual):
            if previous == [c[:3] for c in clues]:
                continue
            slot.conditions.all().delete()
            DailySlotCondition.objects.bulk_create([
                DailySlotCondition(slot=slot, order=i, condition_type=kind, operator=op,
                                   value=value, label_pl=pl, label_en=en)
                for i, (kind, op, value, pl, en) in enumerate(clues)
            ])
        validate_daily(daily)
        for slot in slots:
            self.stdout.write(f'{slot.role}: {len(count_candidates(slot))} candidates')
        if not options['apply']:
            transaction.set_rollback(True)
            self.stdout.write('Preview only; no changes saved. Use --apply to install.')
        else:
            self.stdout.write('Curated board installed; slot IDs preserved.')
