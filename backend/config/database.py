from urllib.parse import parse_qsl, urlsplit

from psycopg2 import ProgrammingError
from psycopg2.extensions import parse_dsn


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
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': parameters.pop('dbname'),
        'USER': parameters.pop('user', ''),
        'PASSWORD': parameters.pop('password', ''),
        'HOST': parameters.pop('host', ''),
        'PORT': parameters.pop('port', '5432'),
        'OPTIONS': parameters,
    }
