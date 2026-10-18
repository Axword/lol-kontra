from contextlib import contextmanager
from copy import deepcopy
from urllib.parse import parse_qsl, urlsplit

from psycopg2 import ProgrammingError
from psycopg2.extensions import parse_dsn


def is_neon_pooler(database):
    hosts = database.get('HOST', '').lower().split(',')
    return any(
        host.rstrip('.').endswith('.neon.tech')
        and host.split('.')[0].endswith('-pooler')
        for host in hosts
    )


def _endpoint(database):
    hosts = []
    for host in database.get('HOST', '').lower().split(','):
        host = host.rstrip('.')
        if is_neon_pooler({'HOST': host}):
            label, domain = host.split('.', 1)
            host = label.removesuffix('-pooler') + '.' + domain
        hosts.append(host)
    return (
        tuple(hosts), str(database.get('PORT') or '5432'),
        database.get('NAME'), database.get('OPTIONS', {}).get('hostaddr', ''),
    )


def postgres_config(database_url):
    """Parse with libpq so TLS options and URI escaping match the actual driver."""
    error = 'DATABASE_URL must be a valid PostgreSQL URL with a database name and unambiguous options'
    try:
        url = urlsplit(database_url)
        if url.scheme not in ('postgres', 'postgresql') or not url.path.strip('/') or url.fragment:
            raise ValueError(error)
        # Reject accidental duplicate options rather than silently weakening e.g. sslmode.
        options = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        if len({name for name, _ in options}) != len(options):
            raise ValueError(error)
        parameters = parse_dsn(database_url)
        if not parameters.get('dbname'):
            raise ValueError(error)
        port = parameters.get('port', '5432')
        if any(value and not 0 < int(value) <= 65535 for value in port.split(',')):
            raise ValueError(error)
    except (TypeError, ValueError, ProgrammingError):
        # Driver errors may contain fragments of the URL, including credentials.
        raise ValueError(error) from None
    database = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parameters.pop('dbname'),
        'USER': parameters.pop('user', ''),
        'PASSWORD': parameters.pop('password', ''),
        'HOST': parameters.pop('host', ''),
        'PORT': parameters.pop('port', '5432'),
        'OPTIONS': parameters,
    }
    if is_neon_pooler(database):
        # PgBouncer transaction pooling cannot keep named cursors on one session.
        database['DISABLE_SERVER_SIDE_CURSORS'] = True
    return database


@contextmanager
def bootstrap_connection(alias, *, database_url=None):
    """Use deployment credentials only within this thread's bootstrap command."""
    from django.db import connections

    runtime = connections[alias]
    if runtime.vendor != 'postgresql':
        raise ValueError('Bootstrap requires PostgreSQL')
    if runtime.in_atomic_block:
        raise ValueError('Bootstrap cannot replace a connection inside an active transaction')
    configuration = deepcopy(runtime.settings_dict)
    if database_url:
        try:
            configuration.update(postgres_config(database_url))
        except ValueError:
            raise ValueError('DATABASE_URL_UNPOOLED must be a valid PostgreSQL connection URL') from None
    if is_neon_pooler(configuration):
        raise ValueError('Bootstrap requires a direct connection; configure DATABASE_URL_UNPOOLED without a Neon pooler')
    if _endpoint(configuration) != _endpoint(runtime.settings_dict):
        raise ValueError('DATABASE_URL_UNPOOLED must target the same database and endpoint as the application connection')

    # Preserve Django's normalized TIME_ZONE, TEST, AUTOCOMMIT and other settings.
    # A distinct wrapper also avoids retaining owner credentials or session state
    # when call_command() runs inside a longer-lived application process.
    owner = runtime.__class__(configuration, alias)
    connections[alias] = owner
    try:
        yield owner
    finally:
        try:
            owner.close()
        finally:
            connections[alias] = runtime
