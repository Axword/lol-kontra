from unittest.mock import MagicMock

import pytest

from .runtime_database import check_runtime_database


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


def test_sixteen_character_password_reaches_role_and_grant_checks(monkeypatch):
    password = 'boundary-pass-12'
    assert len(password) == 16
    monkeypatch.setenv('POSTGRES_APP_USER', 'worlds_app')
    monkeypatch.setenv('POSTGRES_APP_PASSWORD', password)
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
