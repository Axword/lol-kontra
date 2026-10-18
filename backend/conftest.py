"""Keep ordinary model tests independent of the shipped release data.

Production data migrations are exercised separately on a fresh PostgreSQL
database. The game's unit/integration factories intentionally start empty.
"""
import pytest


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    from django.core.management import call_command
    from django.db import connection

    with django_db_blocker.unblock():
        if not str(connection.settings_dict['NAME']).startswith('test_'):
            raise RuntimeError('Refusing to clear a database outside the pytest test_ namespace')
        call_command('flush', interactive=False, verbosity=0)
