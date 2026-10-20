"""Create or validate the VPS env without displaying secret values."""
import argparse
import ipaddress
import os
from pathlib import Path
import re
import secrets


def read_env(path):
    result = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not re.fullmatch(r'[A-Z][A-Z0-9_]*', key) or key in result:
            raise ValueError('Invalid or duplicated environment key')
        # No evaluation, variable interpolation or shell sourcing.
        if value.startswith("'"):
            if not value.endswith("'") or "'" in value[1:-1]:
                raise ValueError('Invalid literal environment value')
            value = value[1:-1]
        elif key == 'DJANGO_SECRET_KEY' and '$' in value:
            raise ValueError('A Django secret containing $ must use literal single quotes')
        result[key] = value
    return result


def validate(values):
    domain = values.get('PUBLIC_DOMAIN', '')
    if (len(domain) > 253 or '.' not in domain or not re.fullmatch(
            r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+', domain)
            or domain.endswith(('.localhost', '.local', '.invalid'))):
        raise ValueError('PUBLIC_DOMAIN must be a bare public DNS name, without a scheme or path')
    try:
        ipaddress.ip_address(domain)
    except ValueError:
        pass
    else:
        raise ValueError('Use a DNS domain for the HTTPS certificate')
    if not re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', values.get('ACME_EMAIL', '')):
        raise ValueError('ACME_EMAIL must be a certificate contact email')
    secret = values.get('DJANGO_SECRET_KEY', '')
    if (len(secret) < 50 or len(set(secret)) < 5 or not re.fullmatch(r'[!-~]+', secret)
            or any(char in secret for char in "'\\")
            or secret.lower().startswith(('django-insecure-', 'dev-secret', 'change-me', 'changeme'))):
        raise ValueError('Use the existing strong Django secret; unsupported quotes/backslashes require a reviewed configuration')
    for key, minimum in [('POSTGRES_PASSWORD', 32), ('POSTGRES_APP_PASSWORD', 32)]:
        value = values.get(key, '')
        if len(value) < minimum or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
            raise ValueError(f'{key} must be a generated URL-safe secret of at least {minimum} characters')
    if len({values[key] for key in ['DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD', 'POSTGRES_APP_PASSWORD']}) != 3:
        raise ValueError('Use three different secrets')
    for key in ['POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_APP_USER']:
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', values.get(key, '')):
            raise ValueError(f'{key} must be a lowercase PostgreSQL identifier')
    if values['POSTGRES_USER'] == values['POSTGRES_APP_USER']:
        raise ValueError('Database owner and runtime role must differ')
    if values.get('POSTGRES_MAJOR') not in {'16', '17', '18'}:
        raise ValueError('Set POSTGRES_MAJOR to 16, 17 or 18, matching the source before importing; never change it on an existing data volume')
    volume_target = '/var/lib/postgresql' if values['POSTGRES_MAJOR'] == '18' else '/var/lib/postgresql/data'
    if values.get('POSTGRES_VOLUME_TARGET', '/var/lib/postgresql/data') != volume_target:
        raise ValueError('POSTGRES_VOLUME_TARGET must match the database image: /var/lib/postgresql for 18, /var/lib/postgresql/data for 16/17; never move an existing data volume')
    if values.get('BACKUP_DIR') != '/var/backups/words-v':
        raise ValueError('BACKUP_DIR must be /var/backups/words-v (mount additional storage there if needed)')
    if any(key.startswith(('DATABASE_', 'NEXT_PUBLIC_')) for key in values):
        raise ValueError('Do not reuse the Neon/development env for the VPS stack')
    return values


def create(path, domain, email, *, django_secret=None, postgres_major='17'):
    values = validate({
        'PUBLIC_DOMAIN': domain, 'ACME_EMAIL': email,
        'DJANGO_SECRET_KEY': secrets.token_urlsafe(60) if django_secret is None else django_secret,
        'POSTGRES_MAJOR': postgres_major,
        'POSTGRES_VOLUME_TARGET': '/var/lib/postgresql' if postgres_major == '18' else '/var/lib/postgresql/data',
        'POSTGRES_DB': 'words_v', 'POSTGRES_USER': 'words_owner',
        'POSTGRES_PASSWORD': secrets.token_urlsafe(36),
        'POSTGRES_APP_USER': 'words_app', 'POSTGRES_APP_PASSWORD': secrets.token_urlsafe(36),
        'BACKUP_DIR': '/var/backups/words-v',
    })
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as stream:
        # Compose uses single-quoted values literally, including $ and # in a
        # migrated Django secret. Never interpolate that secret as shell code.
        stream.write('\n'.join(f"{key}='{value}'" for key, value in values.items()) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['create', 'check', 'domain'])
    parser.add_argument('--file', type=Path, default=Path('/etc/words-v/app.env'))
    parser.add_argument('--domain')
    parser.add_argument('--email')
    parser.add_argument('--postgres-major', choices=['16', '17', '18'], default='17')
    parser.add_argument('--django-secret-file', type=Path)
    parser.add_argument('--new-install', action='store_true')
    args = parser.parse_args()
    try:
        if args.mode == 'create':
            if bool(args.django_secret_file) == args.new_install:
                raise ValueError('For migration provide --django-secret-file; use --new-install only for a new empty app')
            old_secret = args.django_secret_file.read_text(encoding='utf-8').rstrip('\r\n') if args.django_secret_file else None
            create(args.file, args.domain or '', args.email or '', django_secret=old_secret, postgres_major=args.postgres_major)
            print('Created private VPS configuration. Existing files are never overwritten.')
        else:
            values = validate(read_env(args.file))
            print(values['PUBLIC_DOMAIN'] if args.mode == 'domain' else 'VPS configuration OK (secrets hidden)')
    except (ValueError, FileExistsError, OSError) as error:
        if isinstance(error, ValueError):
            parser.exit(1, f'{error}\n')
        parser.exit(1, 'Cannot create/read configuration; check the path and permissions. No secrets were displayed.\n')
