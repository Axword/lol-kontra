"""Compatibility entry point for the retired synthetic-history command."""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Retired: synthetic history is disabled; use prepare_month to create boards without votes'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--subs', type=int, default=0)
        parser.add_argument('--clear', action='store_true')

    def handle(self, *args, **options):
        raise CommandError('Synthetic history is disabled; use prepare_month --month YYYY-MM')

    def simulate_submissions(self, daily, n):
        raise CommandError('Synthetic history is disabled')
