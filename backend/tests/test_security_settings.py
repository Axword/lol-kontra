"""Load settings in isolation; never connect to the running development database."""

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.checks import Tags, run_checks
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.middleware.security import SecurityMiddleware
from django.test import RequestFactory, override_settings


PRODUCTION_ENV = {
    'DJANGO_DEBUG': 'false',
    'DJANGO_SECRET_KEY': 'test-only-production-configuration-key-with-many-characters-12345',
    'DJANGO_ALLOWED_HOSTS': 'roster.example.com,api.roster.example.com',
    'POSTGRES_DB': 'roster',
    'POSTGRES_USER': 'roster_app',
    'POSTGRES_PASSWORD': 'test-only-database-password-12345',
    'POSTGRES_HOST': 'db',
}


def load_settings(environment):
    settings_path = Path(__file__).resolve().parents[1] / 'config' / 'settings.py'
    spec = importlib.util.spec_from_file_location('config.isolated_security_settings', settings_path)
    module = importlib.util.module_from_spec(spec)
    # Do not load the user's real .env or change Django's configured global settings.
    with patch.dict(os.environ, environment, clear=True), patch('dotenv.load_dotenv'):
        spec.loader.exec_module(module)
    return module


def test_production_uses_secure_cookies_and_https_without_trusting_arbitrary_proxy_headers():
    settings = load_settings(PRODUCTION_ENV)
    assert settings.DEBUG is False
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SECURE_HSTS_SECONDS > 0
    assert settings.SECURE_PROXY_SSL_HEADER is None
    assert settings.CORS_ALLOWED_ORIGINS == []
    assert settings.CSRF_TRUSTED_ORIGINS == []
    assert settings.CORS_ALLOW_ALL_ORIGINS is False


def test_proxy_https_header_is_an_explicit_trusted_ingress_setting():
    settings = load_settings({**PRODUCTION_ENV, 'DJANGO_TRUST_PROXY_HEADERS': 'true'})
    assert settings.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')


def test_trusted_https_proxy_does_not_create_a_redirect_loop():
    settings = load_settings({**PRODUCTION_ENV, 'DJANGO_TRUST_PROXY_HEADERS': 'true'})
    with override_settings(
        SECURE_SSL_REDIRECT=settings.SECURE_SSL_REDIRECT,
        SECURE_PROXY_SSL_HEADER=settings.SECURE_PROXY_SSL_HEADER,
        SECURE_HSTS_SECONDS=settings.SECURE_HSTS_SECONDS,
        ALLOWED_HOSTS=settings.ALLOWED_HOSTS,
    ):
        middleware = SecurityMiddleware(lambda request: HttpResponse('ok'))
        secure_request = RequestFactory().get(
            '/api/v1/', HTTP_HOST='roster.example.com', HTTP_X_FORWARDED_PROTO='https',
        )
        response = middleware(secure_request)
        assert response.status_code == 200
        assert response['Strict-Transport-Security'].startswith('max-age=31536000')
        plain_request = RequestFactory().get('/api/v1/', HTTP_HOST='roster.example.com')
        response = middleware(plain_request)
        assert response.status_code == 301
        assert response['Location'] == 'https://roster.example.com/api/v1/'


def test_django_deployment_security_checks_only_leave_optional_hsts_scope_warnings():
    settings = load_settings(PRODUCTION_ENV)
    names = (
        'DEBUG', 'SECRET_KEY', 'ALLOWED_HOSTS', 'MIDDLEWARE', 'SESSION_COOKIE_SECURE',
        'CSRF_COOKIE_SECURE', 'SECURE_SSL_REDIRECT', 'SECURE_HSTS_SECONDS',
        'SECURE_HSTS_INCLUDE_SUBDOMAINS', 'SECURE_HSTS_PRELOAD',
    )
    with override_settings(**{name: getattr(settings, name) for name in names}):
        issues = run_checks(tags=[Tags.security], include_deployment_checks=True)
    # Subdomain coverage and browser preload require the operator's domain policy;
    # enabling them silently can lock unrelated applications out of HTTP.
    assert {issue.id for issue in issues} <= {'security.W005', 'security.W021'}


@pytest.mark.parametrize('secret', [
    None, '', 'short-key', 'a' * 60, 'dev-secret-change-me',
    'change-me-super-secret-key-lol-roster-2026', 'django-insecure-' + 'test-only-secret-' * 5,
])
def test_production_rejects_missing_weak_or_placeholder_secret(secret):
    environment = PRODUCTION_ENV.copy()
    if secret is None:
        environment.pop('DJANGO_SECRET_KEY')
    else:
        environment['DJANGO_SECRET_KEY'] = secret
    with pytest.raises(ImproperlyConfigured, match='DJANGO_SECRET_KEY'):
        load_settings(environment)


@pytest.mark.parametrize('hosts', [
    None, '', ' ', '*', 'roster.example.com,*', '*.example.com',
    'https://example.com', 'example.com:443', 'example.com/path', 'example.com other.example.com',
    '[127.0.0.1', '[127.0.0.1]',
])
def test_production_requires_explicit_valid_hosts(hosts):
    environment = PRODUCTION_ENV.copy()
    if hosts is None:
        environment.pop('DJANGO_ALLOWED_HOSTS')
    else:
        environment['DJANGO_ALLOWED_HOSTS'] = hosts
    with pytest.raises(ImproperlyConfigured, match='DJANGO_ALLOWED_HOSTS'):
        load_settings(environment)


@pytest.mark.parametrize('setting', ['CORS_ALLOWED_ORIGINS', 'CSRF_TRUSTED_ORIGINS'])
@pytest.mark.parametrize('origin', [
    '*', 'http://roster.example.com', 'https://*.example.com',
    'https://user:password@example.com', 'https://example.com/path',
    'https://example.com?query=true', 'https://example.com#fragment',
    'https://example.com:invalid', 'https://example.com:0',
])
def test_production_rejects_wildcard_insecure_or_malformed_origins(setting, origin):
    with pytest.raises(ImproperlyConfigured, match=setting):
        load_settings({**PRODUCTION_ENV, setting: origin})


def test_origin_and_host_lists_are_trimmed_and_empty_entries_removed():
    settings = load_settings({
        **PRODUCTION_ENV,
        'DJANGO_ALLOWED_HOSTS': ' roster.example.com, ,api.roster.example.com,',
        'CORS_ALLOWED_ORIGINS': ' https://roster.example.com, , https://other.example.com:8443,',
        'CSRF_TRUSTED_ORIGINS': 'https://roster.example.com,',
    })
    assert settings.ALLOWED_HOSTS == ['roster.example.com', 'api.roster.example.com']
    assert settings.CORS_ALLOWED_ORIGINS == ['https://roster.example.com', 'https://other.example.com:8443']
    assert settings.CSRF_TRUSTED_ORIGINS == ['https://roster.example.com']


def test_explicit_ipv6_hosts_and_https_origins_are_supported():
    settings = load_settings({
        **PRODUCTION_ENV,
        'DJANGO_ALLOWED_HOSTS': '[2001:db8::1]',
        'CSRF_TRUSTED_ORIGINS': 'https://[2001:db8::1]:8443',
    })
    assert settings.ALLOWED_HOSTS == ['[2001:db8::1]']
    assert settings.CSRF_TRUSTED_ORIGINS == ['https://[2001:db8::1]:8443']


@pytest.mark.parametrize('name', ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_HOST'])
def test_production_does_not_fall_back_to_development_database_credentials(name):
    environment = PRODUCTION_ENV.copy()
    environment.pop(name)
    with pytest.raises(ImproperlyConfigured, match='database|POSTGRES'):
        load_settings(environment)


@pytest.mark.parametrize('password', ['', 'lolroster', 'postgres', 'password', 'change-me'])
def test_production_rejects_default_database_passwords(password):
    with pytest.raises(ImproperlyConfigured, match='database|POSTGRES'):
        load_settings({**PRODUCTION_ENV, 'POSTGRES_PASSWORD': password})


def test_production_database_url_takes_precedence_and_keeps_tls_options():
    environment = {name: value for name, value in PRODUCTION_ENV.items() if not name.startswith('POSTGRES_')}
    environment['DATABASE_URL'] = (
        'postgresql://app:test-only-password-12345@db.example/roster'
        '?sslmode=verify-full&sslrootcert=%2Fcerts%2Froot.pem'
    )
    database = load_settings(environment).DATABASES['default']
    assert database['HOST'] == 'db.example'
    assert database['OPTIONS'] == {'sslmode': 'verify-full', 'sslrootcert': '/certs/root.pem'}


def test_invalid_database_url_is_a_configuration_error_without_leaking_credentials():
    with pytest.raises(ImproperlyConfigured, match='DATABASE_URL') as error:
        load_settings({**PRODUCTION_ENV, 'DATABASE_URL': 'postgresql://u:private-password@db/name?unknown=x'})
    assert 'private-password' not in str(error.value)


def test_runtime_url_takes_precedence_over_owner_and_direct_urls():
    database = load_settings({
        **PRODUCTION_ENV,
        'DATABASE_URL': 'postgresql://owner:owner-password-123456@db.example/owner_db',
        'DATABASE_URL_UNPOOLED': 'postgresql://owner:owner-password-123456@db.example/direct_db',
        'DATABASE_RUNTIME_URL': (
            'postgresql://app:runtime-password-123456@ep-game-pooler.eu-central-1.aws.neon.tech/roster'
            '?sslmode=require&channel_binding=require'
        ),
    }).DATABASES['default']
    assert database['USER'] == 'app'
    assert database['NAME'] == 'roster'
    assert database['DISABLE_SERVER_SIDE_CURSORS'] is True
    assert database['OPTIONS'] == {'sslmode': 'require', 'channel_binding': 'require'}


def test_empty_runtime_url_keeps_existing_database_url_configuration():
    database = load_settings({
        **PRODUCTION_ENV,
        'DATABASE_RUNTIME_URL': '',
        'DATABASE_URL': 'postgresql://app:runtime-password-123456@db.example/roster',
    }).DATABASES['default']
    assert (database['USER'], database['HOST'], database['NAME']) == ('app', 'db.example', 'roster')


def test_invalid_runtime_url_fails_without_owner_fallback_or_exposing_secret():
    with pytest.raises(ImproperlyConfigured, match='DATABASE_RUNTIME_URL') as error:
        load_settings({
            **PRODUCTION_ENV,
            'DATABASE_URL': 'postgresql://owner:owner-password-123456@db.example/roster',
            'DATABASE_RUNTIME_URL': 'postgresql://app:private-runtime-password@db/name?unknown=x',
        })
    assert 'private-runtime-password' not in str(error.value)


@pytest.mark.parametrize('setting', ['DJANGO_DEBUG', 'DJANGO_TRUST_PROXY_HEADERS'])
def test_boolean_typo_is_rejected_instead_of_silently_changing_security_mode(setting):
    with pytest.raises(ImproperlyConfigured, match=setting):
        load_settings({**PRODUCTION_ENV, setting: 'tru'})


def test_development_defaults_continue_to_allow_local_http():
    settings = load_settings({})
    assert settings.DEBUG is True
    assert settings.SECURE_SSL_REDIRECT is False
    assert settings.SESSION_COOKIE_SECURE is False
    assert settings.CSRF_COOKIE_SECURE is False
    assert 'localhost' in settings.ALLOWED_HOSTS
    assert settings.CORS_ALLOWED_ORIGINS == ['http://localhost:3000']


def test_production_serves_manifest_static_assets_after_security_middleware():
    settings = load_settings(PRODUCTION_ENV)
    security = settings.MIDDLEWARE.index('django.middleware.security.SecurityMiddleware')
    assert settings.MIDDLEWARE[security + 1] == 'whitenoise.middleware.WhiteNoiseMiddleware'
    assert settings.STORAGES['staticfiles']['BACKEND'] == (
        'whitenoise.storage.CompressedManifestStaticFilesStorage'
    )


def test_development_static_urls_do_not_require_a_collected_manifest():
    settings = load_settings({})
    assert settings.STORAGES['staticfiles']['BACKEND'] == (
        'django.contrib.staticfiles.storage.StaticFilesStorage'
    )
