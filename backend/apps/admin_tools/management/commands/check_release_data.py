from django.core.management.base import BaseCommand, CommandError
from apps.admin_tools.release_checks import check_release_data


class Command(BaseCommand):
    help = 'Verify migrated offline release data without changing the database'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')
        parser.add_argument('--strict', action='store_true', help='Require the exact fresh-install release data')

    def handle(self, *args, **options):
        try:
            report = check_release_data(database=options['database'], strict=options['strict'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS('Release data verified: ' + ', '.join(f'{key}={value}' for key, value in report.items())))
