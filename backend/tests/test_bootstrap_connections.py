"""Deployment connection tests use synthetic URLs and never open a database."""
from copy import deepcopy
from importlib import import_module
from io import StringIO
from unittest.mock import MagicMock, sentinel

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.db.utils import ConnectionHandler

from config.database import bootstrap_connection, postgres_config


RUNTIME_URL = 'postgresql://app:runtime-password-123456@ep-game-pooler.eu-central-1.aws.neon.tech/roster?sslmode=require'
DIRECT_URL = 'postgresql://owner:owner-password-123456@ep-game.eu-central-1.aws.neon.tech/roster?sslmode=require&channel_binding=require'
command = import_module('apps.admin_tools.management.commands.bootstrap_database')


@pytest.fixture
def handlers(monkeypatch):
    configuration = {
        **postgres_config(RUNTIME_URL), 'TIME_ZONE': 'Europe/Warsaw',
        'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True, 'ATOMIC_REQUESTS': True,
        'TEST': {'NAME': 'test_roster', 'MIGRATE': False},
    }
    handlers = ConnectionHandler({'default': configuration, 'archive': deepcopy(configuration)})
    # The context imports this registry dynamically; no real default connection
    # or .env value is used by these tests.
    monkeypatch.setattr('django.db.connections', handlers)
    monkeypatch.setenv('DATABASE_URL_UNPOOLED', DIRECT_URL)
    return handlers


@pytest.mark.parametrize('fails', [False, True])
def test_context_preserves_runtime_connection_and_complete_django_configuration(handlers, fails):
    runtime = handlers['default']
    archive = handlers['archive']
    original = deepcopy(runtime.settings_dict)
    owner = None
    try:
        with bootstrap_connection('default', database_url=DIRECT_URL) as owner:
            owner.close = MagicMock()
            assert handlers['default'] is owner
            assert handlers['archive'] is archive
            assert owner.settings_dict['USER'] == 'owner'
            assert owner.settings_dict['HOST'] == 'ep-game.eu-central-1.aws.neon.tech'
            assert owner.settings_dict['OPTIONS'] == {'sslmode': 'require', 'channel_binding': 'require'}
            for key in ('TIME_ZONE', 'CONN_MAX_AGE', 'CONN_HEALTH_CHECKS', 'AUTOCOMMIT', 'ATOMIC_REQUESTS', 'TEST'):
                assert owner.settings_dict[key] == original[key]
            owner.settings_dict['TEST']['NAME'] = 'temporary'
            if fails:
                raise RuntimeError('Migration failed')
    except RuntimeError:
        assert fails
    assert handlers['default'] is runtime
    assert runtime.settings_dict == original
    assert handlers.settings['default'] == original
    owner.close.assert_called_once_with()


@pytest.mark.parametrize('url', [RUNTIME_URL, None])
def test_pooler_is_rejected_before_opening_or_replacing_any_connection(handlers, url):
    runtime = handlers['default']
    runtime.ensure_connection = MagicMock()
    with pytest.raises(ValueError, match='direct connection'):
        with bootstrap_connection('default', database_url=url):
            pytest.fail('A session advisory lock must not run through a pooler')
    assert handlers['default'] is runtime
    runtime.ensure_connection.assert_not_called()


@pytest.mark.parametrize('url', [
    DIRECT_URL.replace('/roster?', '/different_db?'),
    DIRECT_URL.replace('ep-game.', 'ep-production.'),
    DIRECT_URL.replace('/roster?', ':5433/roster?'),
    DIRECT_URL + '&hostaddr=192.0.2.10',
])
def test_other_database_or_endpoint_cannot_redirect_local_bootstrap_to_production(handlers, url):
    runtime = handlers['default']
    with pytest.raises(ValueError, match='same database and endpoint'):
        with bootstrap_connection('default', database_url=url):
            pytest.fail('Conflicting deployment URL must never connect')
    assert handlers['default'] is runtime


def test_invalid_direct_url_is_redacted_and_does_not_change_runtime(handlers):
    runtime = handlers['default']
    with pytest.raises(ValueError, match='DATABASE_URL_UNPOOLED') as error:
        with bootstrap_connection('default', database_url=DIRECT_URL + '&unknown=private-secret'):
            pytest.fail('Invalid URL must fail before replacement')
    assert 'private-secret' not in str(error.value)
    assert 'owner-password' not in str(error.value)
    assert handlers['default'] is runtime


def test_bootstrap_refuses_to_escape_an_existing_application_transaction(handlers):
    runtime = handlers['default']
    runtime.in_atomic_block = True
    with pytest.raises(ValueError, match='active transaction'):
        with bootstrap_connection('default', database_url=DIRECT_URL):
            pytest.fail('Bootstrap must not commit outside its caller transaction')
    assert handlers['default'] is runtime


def test_runtime_is_restored_even_if_owner_connection_cleanup_fails(handlers):
    runtime = handlers['default']
    with pytest.raises(OperationalError, match='Close failed'):
        with bootstrap_connection('default', database_url=DIRECT_URL) as owner:
            owner.close = MagicMock(side_effect=OperationalError('Close failed'))
    assert handlers['default'] is runtime


@pytest.mark.parametrize('failure', [None, 'migration', 'runtime_guard', 'connect_timeout'])
def test_bootstrap_uses_owner_for_all_deployment_steps_then_restores_runtime(handlers, monkeypatch, failure):
    runtime = handlers['default']
    original = deepcopy(runtime.settings_dict)
    opened, closed = [], []
    cursor = MagicMock()
    cursor.__enter__.return_value.fetchone.return_value = (True,)

    def ensure_connection(owner):
        opened.append(owner)
        assert owner is handlers['default'] and owner is not runtime
        assert owner.settings_dict['USER'] == 'owner'
        if failure == 'connect_timeout':
            raise OperationalError('Synthetic timeout')
        owner.connection = sentinel.owner_connection

    def close(owner):
        closed.append(owner)
        owner.connection = None

    monkeypatch.setattr(type(runtime), 'ensure_connection', ensure_connection)
    monkeypatch.setattr(type(runtime), 'close', close)
    monkeypatch.setattr(type(runtime), 'cursor', lambda self: cursor)
    migrate = MagicMock(side_effect=RuntimeError('Migration failed') if failure == 'migration' else None)
    monkeypatch.setattr(command, 'call_command', migrate)
    release = MagicMock(return_value={'players': 882, 'verified': 738, 'boards': 31})
    monkeypatch.setattr(command, 'check_release_data', release)

    def guard(owner):
        assert owner is handlers['default'] and owner.settings_dict['USER'] == 'owner'
        if failure == 'runtime_guard':
            raise ValueError('Runtime role lacks grants')

    monkeypatch.setattr(command, 'check_runtime_database', guard)
    if failure == 'connect_timeout':
        times = iter([0, 2])
        monkeypatch.setattr(command, 'monotonic', lambda: next(times))

    if failure:
        error = RuntimeError if failure == 'migration' else CommandError
        with pytest.raises(error):
            call_command('bootstrap_database', skip_today=True, timeout=1, stdout=StringIO(), skip_checks=True)
    else:
        call_command('bootstrap_database', skip_today=True, timeout=1, stdout=StringIO(), skip_checks=True)

    assert handlers['default'] is runtime
    assert runtime.settings_dict == original
    assert opened and all(owner is not runtime for owner in closed)
    assert closed[-1] is opened[0]
    if failure != 'connect_timeout':
        migrate.assert_called_once_with('migrate', database='default', interactive=False, verbosity=1)
        executed = [call.args[0] for call in cursor.__enter__.return_value.execute.call_args_list]
        assert 'SELECT pg_try_advisory_lock(%s)' in executed
        assert executed[-1] == 'SELECT pg_advisory_unlock(%s)'
    else:
        migrate.assert_not_called()
        release.assert_not_called()


def test_explicit_database_alias_is_not_redirected_by_default_neon_environment(handlers, monkeypatch):
    handlers['archive'].settings_dict.update(postgres_config(DIRECT_URL.replace('owner:', 'archive_owner:')))
    original = handlers['archive']
    monkeypatch.setenv('DATABASE_URL_UNPOOLED', DIRECT_URL.replace('ep-game.', 'ep-unrelated-production.'))

    def initialize(self, connection, alias, timeout, options):
        assert alias == 'archive'
        assert connection.settings_dict['USER'] == 'archive_owner'
        assert connection.settings_dict['HOST'] == 'ep-game.eu-central-1.aws.neon.tech'
        connection.close = MagicMock()

    monkeypatch.setattr(command.Command, 'initialize', initialize)
    call_command('bootstrap_database', database='archive', skip_today=True, stdout=StringIO(), skip_checks=True)
    assert handlers['archive'] is original
