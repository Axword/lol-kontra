import pytest

from config.database import postgres_config


def test_database_url_overrides_docker_host_and_decodes_credentials():
    database = postgres_config('postgres://some%40user:p%40ss%3Aword@127.0.0.1:5433/roster%2Dtest')
    assert database['HOST'] == '127.0.0.1'
    assert database['PORT'] == '5433'
    assert database['NAME'] == 'roster-test'
    assert database['USER'] == 'some@user'
    assert database['PASSWORD'] == 'p@ss:word'


def test_database_url_preserves_connection_options():
    database = postgres_config('postgresql://user:pass@localhost/roster?sslmode=require&connect_timeout=5')
    assert database['PORT'] == '5432'
    assert database['OPTIONS'] == {'sslmode': 'require', 'connect_timeout': '5'}


def test_ssl_certificates_and_blank_options_are_not_discarded():
    database = postgres_config(
        'postgresql://user:pass@db.example/roster?sslmode=verify-full'
        '&sslrootcert=%2Fcerts%2Fca.pem&sslcert=%2Fcerts%2Fclient.pem'
        '&sslkey=%2Fcerts%2Fclient.key&application_name='
    )
    assert database['OPTIONS'] == {
        'sslmode': 'verify-full',
        'sslrootcert': '/certs/ca.pem',
        'sslcert': '/certs/client.pem',
        'sslkey': '/certs/client.key',
        'application_name': '',
    }


def test_url_options_follow_libpq_uri_encoding_without_turning_plus_into_space():
    database = postgres_config('postgresql://user:pass@db/roster?application_name=roster+worker')
    assert database['OPTIONS']['application_name'] == 'roster+worker'


def test_connection_parameters_in_query_are_not_shadowed_by_django_defaults():
    database = postgres_config('postgresql:///roster?host=%2Fvar%2Frun%2Fpostgresql&user=app&port=5433')
    assert database['HOST'] == '/var/run/postgresql'
    assert database['USER'] == 'app'
    assert database['PORT'] == '5433'
    assert database['OPTIONS'] == {}


@pytest.mark.parametrize('url', [
    'sqlite:///roster',
    'postgres://localhost/',
    'postgres://localhost/roster#sslmode=require',
    'postgres://localhost:invalid/roster',
    'postgres://localhost:0/roster',
    'postgres://localhost:65536/roster',
    'postgres://localhost/roster?sslmode=require&sslmode=disable',
    'postgres://localhost/roster?unknown_connection_option=ignored',
    'postgres://localhost/roster?sslmode',
    'postgres://localhost/roster?sslrootcert=%invalid',
])
def test_invalid_database_urls_fail_explicitly(url):
    with pytest.raises(ValueError):
        postgres_config(url)


def test_invalid_url_does_not_leak_credentials_in_error():
    with pytest.raises(ValueError) as error:
        postgres_config('postgresql://user:private-password@db/roster?unknown_connection_option=x')
    assert 'private-password' not in str(error.value)
