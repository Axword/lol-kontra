from unittest.mock import MagicMock

import pytest

from .runtime_database import check_runtime_database


@pytest.fixture(autouse=True)
def isolated_runtime_credentials(monkeypatch):
    for name in ('DATABASE_RUNTIME_URL', 'POSTGRES_APP_USER', 'POSTGRES_APP_PASSWORD'):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize('password', [
    'short-secret', 'x' * 15, 'lolroster', 'postgres', 'password', 'change-me', 'changeme',
])
def test_weak_runtime_password_fails_before_any_sql_or_connection(monkeypatch, password):
    monkeypatch.setenv('POSTGRES_APP_USER', 'worlds_app')
    monkeypatch.setenv('POSTGRES_APP_PASSWORD', password)
    owner = MagicMock()
    owner.settings_dict = {'USER': 'worlds_owner'}
    connect = MagicMock(side_effect=AssertionError('Preflight must not open a connection'))
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)

    with pytest.raises(ValueError) as error:
        check_runtime_database(owner)

    assert password not in str(error.value)
    owner.cursor.assert_not_called()
    owner.get_connection_params.assert_not_called()
    connect.assert_not_called()


@pytest.mark.parametrize('credential_source', ['legacy', 'url', 'matching_url_and_legacy'])
def test_sixteen_character_password_reaches_role_and_grant_checks(monkeypatch, credential_source):
    password = 'boundary-pass-12'
    assert len(password) == 16
    if credential_source != 'url':
        monkeypatch.setenv('POSTGRES_APP_USER', 'worlds_app')
        monkeypatch.setenv('POSTGRES_APP_PASSWORD', password)
    if credential_source != 'legacy':
        monkeypatch.setenv('DATABASE_RUNTIME_URL', f'postgresql://worlds_app:{password}@db/worlds?sslmode=require')
    owner = MagicMock()
    owner.settings_dict = {'USER': 'worlds_owner'}
    owner.get_connection_params.return_value = {'dbname': 'worlds', 'user': 'worlds_owner'}
    owner.cursor.return_value.__enter__.return_value.fetchone.return_value = (123, False)
    runtime = MagicMock()
    cursor = runtime.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [('django_migrations',)]
    cursor.fetchone.side_effect = [
        (False, False, False, False),  # No administrative role flags.
        (False,),  # Cannot create schema objects.
        (True,),  # Can read migration history.
        (True,),  # Can use sequences.
        (False,),  # Cannot update migration history.
    ]
    connect = MagicMock(return_value=runtime)
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)

    check_runtime_database(owner)

    owner.cursor.assert_called_once()
    assert owner.cursor.return_value.__enter__.return_value.execute.call_args_list[0].args[1] == ['worlds_app']
    connect.assert_called_once_with(dbname='worlds', user='worlds_app', password=password, connect_timeout=10)


@pytest.mark.parametrize('role_state', [(123, True), None])
def test_owner_membership_or_missing_role_fails_before_revoke_or_runtime_connection(monkeypatch, role_state):
    monkeypatch.setenv('POSTGRES_APP_USER', 'worlds_app')
    monkeypatch.setenv('POSTGRES_APP_PASSWORD', 'boundary-pass-12')
    owner = MagicMock()
    owner.settings_dict = {'USER': 'worlds_owner'}
    owner_cursor = owner.cursor.return_value.__enter__.return_value
    owner_cursor.fetchone.return_value = role_state
    connect = MagicMock(side_effect=AssertionError('Unsafe role must not connect'))
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)

    with pytest.raises(ValueError):
        check_runtime_database(owner)

    assert owner_cursor.execute.call_count == 1
    assert owner_cursor.execute.call_args.args[0].lstrip().startswith('SELECT')
    owner.get_connection_params.assert_not_called()
    connect.assert_not_called()


def test_no_runtime_configuration_keeps_legacy_optional_behavior(monkeypatch):
    owner = MagicMock()
    connect = MagicMock()
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)
    check_runtime_database(owner)
    owner.cursor.assert_not_called()
    owner.get_connection_params.assert_not_called()
    connect.assert_not_called()


@pytest.mark.parametrize('legacy', [
    {'POSTGRES_APP_USER': 'different_app', 'POSTGRES_APP_PASSWORD': 'boundary-pass-12'},
    {'POSTGRES_APP_USER': 'worlds_app', 'POSTGRES_APP_PASSWORD': 'different-password-123'},
    {'POSTGRES_APP_USER': 'worlds_app'},
    {'POSTGRES_APP_PASSWORD': 'boundary-pass-12'},
])
def test_runtime_url_conflicts_with_legacy_credentials_before_any_sql_or_network(monkeypatch, legacy):
    monkeypatch.setenv('DATABASE_RUNTIME_URL', 'postgresql://worlds_app:boundary-pass-12@db/worlds')
    for name, value in legacy.items():
        monkeypatch.setenv(name, value)
    owner = MagicMock()
    owner.settings_dict = {'USER': 'worlds_owner'}
    connect = MagicMock()
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)
    with pytest.raises(ValueError) as error:
        check_runtime_database(owner)
    assert 'boundary-pass-12' not in str(error.value)
    assert 'different-password-123' not in str(error.value)
    owner.cursor.assert_not_called()
    owner.get_connection_params.assert_not_called()
    connect.assert_not_called()


@pytest.mark.parametrize('runtime_url', [
    '',
    'postgresql://app:private-url-secret@db/worlds?unknown_option=x',
    'postgresql://app:private-url-secret@db/worlds?sslmode=require&sslmode=disable',
    'postgresql://app@db/worlds',
    'postgresql://:private-url-secret@db/worlds',
    'postgresql://app:short-secret@db/worlds',
    'postgresql://worlds_owner:private-url-secret@db/worlds',
])
def test_invalid_or_owner_runtime_url_cannot_bypass_checks_or_expose_secrets(monkeypatch, runtime_url):
    monkeypatch.setenv('DATABASE_RUNTIME_URL', runtime_url)
    owner = MagicMock()
    owner.settings_dict = {'USER': 'worlds_owner'}
    connect = MagicMock()
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)
    with pytest.raises(ValueError) as error:
        check_runtime_database(owner)
    assert 'private-url-secret' not in str(error.value)
    assert 'short-secret' not in str(error.value)
    owner.cursor.assert_not_called()
    owner.get_connection_params.assert_not_called()
    connect.assert_not_called()


def test_url_only_role_still_must_be_isolated_from_owner_or_admin_roles(monkeypatch):
    monkeypatch.setenv('DATABASE_RUNTIME_URL', 'postgresql://worlds_app:boundary-pass-12@db/worlds')
    owner = MagicMock()
    owner.settings_dict = {'USER': 'worlds_owner'}
    cursor = owner.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (123, True)
    connect = MagicMock()
    monkeypatch.setattr('apps.admin_tools.runtime_database.psycopg2.connect', connect)
    with pytest.raises(ValueError, match='isolated'):
        check_runtime_database(owner)
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[1] == ['worlds_app']
    owner.get_connection_params.assert_not_called()
    connect.assert_not_called()
