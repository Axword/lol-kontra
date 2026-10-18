"""Prepare boards without manufacturing players' answers or popularity data."""
import calendar
from datetime import date, datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.dailies.generator import generate_daily, validate_daily


class Command(BaseCommand):
    help = 'Prepare a month of boards without test votes; future dates remain inaccessible through public APIs'

    def add_arguments(self, parser):
        parser.add_argument('--month', required=True, help='YYYY-MM')
        parser.add_argument('--voters', type=int, default=0, help='Deprecated; only 0 is accepted')

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            month = datetime.strptime(options['month'], '%Y-%m').date()
        except ValueError as error:
            raise CommandError('month must be YYYY-MM') from error
        if options['voters'] != 0:
            raise CommandError('Synthetic votes are disabled; omit --voters or use --voters 0')
        today = timezone.localdate()
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
            self.stdout.write(f'{board_date}: ' + ('hidden until its date' if board_date > today else 'available'))
        self.stdout.write(self.style.SUCCESS(f'Prepared {options["month"]}; no synthetic votes. Existing answers preserved.'))
