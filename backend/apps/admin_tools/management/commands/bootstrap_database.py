"""Serialize deployment initialization on PostgreSQL itself."""
import os
from time import monotonic, sleep
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import OperationalError
from django.utils import timezone
from config.database import bootstrap_connection
from apps.admin_tools.release_checks import check_release_data
from apps.admin_tools.runtime_database import check_runtime_database
from apps.dailies.generator import validate_daily
from apps.dailies.models import Daily

LOCK_ID = 836432807102026


class Command(BaseCommand):
    help = 'Wait for PostgreSQL, lock initialization, migrate and verify the offline data release'

    def add_arguments(self, parser):
        parser.add_argument('--database', default='default')
        parser.add_argument('--timeout', type=int, default=120)
        parser.add_argument('--skip-today', action='store_true')

    def handle(self, *args, **options):
        alias, timeout = options['database'], options['timeout']
        if timeout < 1:
            raise CommandError('Bootstrap requires PostgreSQL and a positive timeout')
        if alias != 'default' and not options['skip_today']:
            raise CommandError('Use --skip-today when initializing another database alias')
        # An explicit alternative alias must never be redirected to the default
        # Neon deployment by an unrelated environment variable.
        direct_url = os.getenv('DATABASE_URL_UNPOOLED') if alias == 'default' else None
        try:
            with bootstrap_connection(alias, database_url=direct_url) as connection:
                self.initialize(connection, alias, timeout, options)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CommandError(f'Database initialization stopped: {error}') from error

    def initialize(self, connection, alias, timeout, options):
        connection.settings_dict.setdefault('OPTIONS', {}).setdefault('connect_timeout', min(timeout, 10))
        deadline = monotonic() + timeout
        while True:
            try:
                connection.ensure_connection()
                break
            except OperationalError:
                connection.close()
                if monotonic() >= deadline:
                    raise CommandError('PostgreSQL is unavailable; initialization stopped') from None
                sleep(1)
        locked = False
        try:
            while not locked:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_try_advisory_lock(%s)', [LOCK_ID])
                    locked = cursor.fetchone()[0]
                if not locked:
                    if monotonic() >= deadline:
                        raise CommandError('Another instance is initializing this database; timed out')
                    sleep(1)
            call_command('migrate', database=alias, interactive=False, verbosity=options['verbosity'])
            report = check_release_data(database=alias)
            check_runtime_database(connection)
            if not options['skip_today']:
                today = Daily.objects.filter(date=timezone.localdate()).first()
                if today is None:
                    call_command('create_daily', publish=True, verbosity=options['verbosity'])
                elif today.status != 'draft':
                    validate_daily(today)
            self.stdout.write(self.style.SUCCESS(f"Database ready: {report['players']} identities, {report['verified']} verified players, {report['boards']} October boards"))
        finally:
            if locked and connection.connection is not None:
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_unlock(%s)', [LOCK_ID])
