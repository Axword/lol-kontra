"""Create a full calendar and explicitly marked, repeatable development votes."""
import calendar
import random
from datetime import date, datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.dailies.generator import generate_daily, count_candidates, validate_daily
from apps.scoring.engine import score_daily
from apps.submissions.models import Submission, SubmissionAnswer, SubmissionAttempt


class Command(BaseCommand):
    help = 'Prepare a month with ten marked test voters; future dates remain inaccessible through public APIs'

    def add_arguments(self, parser):
        parser.add_argument('--month', required=True, help='YYYY-MM')
        parser.add_argument('--voters', type=int, default=10)

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            month = datetime.strptime(options['month'], '%Y-%m').date()
        except ValueError as error:
            raise CommandError('month must be YYYY-MM') from error
        voters = options['voters']
        if not 1 <= voters <= 100:
            raise CommandError('voters must be between 1 and 100')
        today = timezone.localdate()
        created_votes = 0
        for day in range(1, calendar.monthrange(month.year, month.month)[1] + 1):
            board_date = date(month.year, month.month, day)
            daily = generate_daily(date=board_date, seed=f'calendar-{board_date}')
            validate_daily(daily)
            if daily.status == 'draft':
                # Public availability is date-gated, so the board opens on its
                # Warsaw date without a scheduler or exposing future content.
                daily.status = 'published'
                daily.published_at = timezone.make_aware(datetime.combine(board_date, time.min))
                daily.save(update_fields=['status', 'published_at'])
            slots = list(daily.slots.prefetch_related('conditions'))
            pools = [sorted(count_candidates(slot), key=lambda player: (-player.worlds_count, player.slug)) for slot in slots]
            for voter in range(1, voters + 1):
                token = f'seed-{board_date}-{voter:02d}'
                submission, _created = Submission.objects.get_or_create(
                    daily=daily, user=None, guest_token=token, is_practice=False,
                    defaults={'is_seed': True},
                )
                if not submission.is_seed:
                    raise CommandError('Seed identity belongs to a real submission')
                existing = {answer.daily_slot_id: answer for answer in submission.answers.all()}
                used = {answer.player_id for answer in existing.values()}
                rng = random.Random(f'{board_date}-voter-{voter}')
                for slot, pool in zip(slots, pools):
                    if slot.id in existing:
                        continue
                    available = [player for player in pool if player.id not in used]
                    if not available:
                        raise CommandError('No distinct test roster is available')
                    if voter <= 4:
                        player = available[0]
                    elif voter <= 7:
                        player = rng.choices(available, weights=[1 / (index + 1) for index in range(len(available))])[0]
                    else:
                        player = rng.choice(available)
                    used.add(player.id)
                    SubmissionAnswer.objects.create(submission=submission, daily_slot=slot, player=player,
                                                     is_correct=True, points_awarded=0)
                    SubmissionAttempt.objects.create(submission=submission, daily_slot=slot, player=player, is_correct=True)
                    created_votes += 1
            score_daily(daily.id, finalize=False)
            self.stdout.write(f'{board_date}: {voters} test rosters; ' + ('hidden until its date' if board_date > today else 'available'))
        self.stdout.write(self.style.SUCCESS(f'Prepared {options["month"]}; {created_votes} new test votes. Existing answers preserved.'))
