import random
from datetime import timedelta
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.dailies.generator import count_candidates, generate_daily
from apps.dailies.models import Daily
from apps.scoring.engine import score_daily
from apps.submissions.models import Submission, SubmissionAnswer


class Command(BaseCommand):
    help = 'Seed historical challenges with validated simulated rosters'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--subs', type=int, default=550, help='submissions per day')
        parser.add_argument('--clear', action='store_true')

    def handle(self, *args, **options):
        days, submissions = options['days'], options['subs']
        if days < 0 or submissions < 0:
            raise CommandError('Days and submissions must be nonnegative')
        today = timezone.localdate()
        if options['clear']:
            Daily.objects.filter(date__lt=today).delete()
        for offset in range(days, 0, -1):
            challenge_date = today - timedelta(days=offset)
            try:
                with transaction.atomic():
                    daily = generate_daily(date=challenge_date, seed=str(challenge_date))
                    daily.status = 'published'
                    daily.published_at = daily.published_at or timezone.now()
                    daily.save(update_fields=['status', 'published_at'])
                    if daily.submissions.count() < 10:
                        self.simulate_submissions(daily, submissions)
                    score_daily(daily.id)
                    daily.status = 'scored'
                    daily.closed_at = timezone.now()
                    daily.save(update_fields=['status', 'closed_at'])
            except ValueError as error:
                raise CommandError(f'Cannot seed {challenge_date}: {error}') from error
            self.stdout.write(self.style.SUCCESS(f'{daily}: {daily.submissions.count()} validated submissions'))

    def simulate_submissions(self, daily, n):
        slots = list(daily.slots.prefetch_related('conditions'))
        candidates = {slot.id: count_candidates(slot) for slot in slots}
        if not slots or any(not candidates[slot.id] for slot in slots):
            raise ValueError('Cannot simulate an incomplete or unsolvable board')
        rnd = random.Random(f'history-{daily.date}')

        def choose_roster():
            roster = {}
            used = set()
            order = sorted(slots, key=lambda slot: len(candidates[slot.id]))

            def choose(index):
                if index == len(order):
                    return True
                slot = order[index]
                weighted = sorted(candidates[slot.id], key=lambda player: rnd.random() ** (
                    1 / (1 + player.worlds_count * 2 + player.worlds_titles_count * 5)))
                for player in reversed(weighted):
                    if player.pk in used:
                        continue
                    roster[slot.id] = player
                    used.add(player.pk)
                    if choose(index + 1):
                        return True
                    used.remove(player.pk)
                    roster.pop(slot.id)
                return False

            if not choose(0):
                raise ValueError('Cannot create a roster with five different players')
            return roster

        for _ in range(n):
            roster = choose_roster()
            submission = Submission.objects.create(
                daily=daily, guest_token=f'sim_{daily.id}_{uuid4().hex}', ip_hash='sim',
            )
            SubmissionAnswer.objects.bulk_create([
                SubmissionAnswer(submission=submission, daily_slot=slot,
                                 player=roster[slot.id], is_correct=True)
                for slot in slots
            ])
        return n
