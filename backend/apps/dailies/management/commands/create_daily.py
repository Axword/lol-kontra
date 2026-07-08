from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.dailies.generator import generate_daily

class Command(BaseCommand):
    help = 'Generate a Daily Challenge'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='YYYY-MM-DD')
        parser.add_argument('--publish', action='store_true')

    def handle(self, *args, **options):
        date_str = options.get('date')
        if date_str:
            from datetime import datetime
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.localdate()
        daily = generate_daily(date=date)
        if options['publish']:
            daily.status = 'published'
            daily.published_at = timezone.now()
            daily.save()
        self.stdout.write(self.style.SUCCESS(f'Created {daily} with {daily.slots.count()} slots'))
        for slot in daily.slots.all():
            self.stdout.write(f"  {slot.role}:")
            for c in slot.conditions.all():
                self.stdout.write(f"    - {c.label_pl}")
