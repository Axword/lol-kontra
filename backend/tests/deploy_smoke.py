"""Exercise real migrations twice on a disposable PostgreSQL database.

Run: python -m tests.deploy_smoke
Requires a database owner with CREATEDB/CREATEROLE. Never alters the application
database. The generated database and role are removed even when a check fails.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import quote, urlencode
import uuid

import psycopg2
from psycopg2 import sql

from config.database import postgres_config

ROOT = Path(__file__).resolve().parents[1]


def run(environment, *arguments):
    result = subprocess.run([sys.executable, 'manage.py', *arguments], cwd=ROOT,
                            env=environment, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        print(result.stdout, end='')
        print(result.stderr, file=sys.stderr, end='')
        raise RuntimeError('Deployment smoke command failed: ' + arguments[0])
    print(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else arguments[0] + ': OK')


def checksum(connection):
    digest = hashlib.sha256()
    with connection.cursor() as cursor:
        for table in ('players_player', 'dailies_daily', 'dailies_dailyslot', 'dailies_dailyslotcondition',
                      'submissions_submission', 'submissions_submissionanswer', 'submissions_submissionattempt',
                      'scoring_answerstatsdaily'):
            cursor.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY id').format(sql.Identifier(table)))
            for row in cursor:
                digest.update(row[0].encode('utf-8'))
    return digest.hexdigest()


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT.parent / '.env')
    if not os.getenv('DATABASE_URL'):
        raise RuntimeError('Set DATABASE_URL for the local test server')
    config = postgres_config(os.environ['DATABASE_URL'])
    parameters = {**config['OPTIONS'], 'dbname': config['NAME'], 'user': config['USER'],
                  'password': config['PASSWORD'], 'host': config['HOST'], 'port': config['PORT']}
    tag = uuid.uuid4().hex[:12]
    database, role = 'test_release_' + tag, 'release_runtime_' + tag
    password = secrets.token_hex(24)
    admin = psycopg2.connect(**parameters)
    admin.autocommit = True
    created_database = created_role = False
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
            created_database = True
            cursor.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION').format(sql.Identifier(role), sql.Literal(password)))
            created_role = True
        fresh_parameters = {**parameters, 'dbname': database}
        with psycopg2.connect(**fresh_parameters) as fresh:
            with fresh.cursor() as cursor:
                cursor.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
                cursor.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
                cursor.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO {}').format(sql.Identifier(role)))
                cursor.execute(sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO {}').format(sql.Identifier(role)))
        uri_parameters = {key: value for key, value in parameters.items() if key != 'dbname'}
        environment = {**os.environ, 'DATABASE_URL': 'postgresql:///' + quote(database, safe='') + '?' + urlencode(uri_parameters),
            'POSTGRES_DB': database, 'POSTGRES_APP_USER': role, 'POSTGRES_APP_PASSWORD': password,
            'DJANGO_SETTINGS_MODULE': 'config.settings', 'DJANGO_DEBUG': 'true',
            'DJANGO_ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver', 'DAILY_TIMEZONE': 'Europe/Warsaw',
            'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'}
        run(environment, 'bootstrap_database', '--skip-today')
        run(environment, 'check_release_data', '--strict')
        fresh = psycopg2.connect(**fresh_parameters)
        try:
            with fresh.cursor() as cursor:
                expected = {'players_player': 882, 'dailies_daily': 31, 'dailies_dailyslot': 155,
                    'dailies_dailyslotcondition': 310, 'submissions_submission': 310,
                    'submissions_submissionanswer': 1550, 'submissions_submissionattempt': 1550}
                for table, count in expected.items():
                    cursor.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table)))
                    assert cursor.fetchone()[0] == count, table
                cursor.execute('SELECT COUNT(*) FROM auth_user')
                assert cursor.fetchone()[0] == 0, 'Release must not ship local accounts'
                cursor.execute("INSERT INTO submissions_submission (daily_id,guest_token,submitted_at,ip_hash,is_scored,is_practice,is_seed,total_points,errors_used) SELECT id,'release-smoke-progress',NOW(),'',false,false,false,500,0 FROM dailies_daily ORDER BY date LIMIT 1 RETURNING id")
                progress_id = cursor.fetchone()[0]
            fresh.commit()
            before = checksum(fresh)
            run(environment, 'bootstrap_database', '--skip-today')
            fresh.rollback()
            assert checksum(fresh) == before, 'Repeated deploy changed release data or player progress'
            with fresh.cursor() as cursor:
                cursor.execute('SELECT total_points FROM submissions_submission WHERE id=%s', [progress_id])
                assert cursor.fetchone()[0] == 500
        finally:
            fresh.close()
        with psycopg2.connect(**{**fresh_parameters, 'user': role, 'password': password}) as runtime:
            with runtime.cursor() as cursor:
                cursor.execute('SELECT COUNT(*) FROM players_player')
                assert cursor.fetchone()[0] == 882
                for statement in ('CREATE TABLE public.must_not_create (id integer)',
                                  'UPDATE django_migrations SET name=name WHERE false'):
                    try:
                        cursor.execute(statement)
                    except psycopg2.errors.InsufficientPrivilege:
                        runtime.rollback()
                    else:
                        raise AssertionError('Runtime role was allowed to change schema or migration history')
        run(environment, 'shell', '-c', API_CHECK)
        print('PASS: fresh migrations, release contents, repeat deploy, progress preservation, private future boards and restricted runtime role')
    finally:
        with admin.cursor() as cursor:
            if created_database:
                cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
            if created_role:
                cursor.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))
        admin.close()


API_CHECK = '''
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.dailies.models import Daily
from apps.dailies.generator import validate_daily
from apps.submissions.models import Submission
with override_settings(CACHES={'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}):
    client=APIClient(HTTP_HOST='localhost')
    for board in Daily.objects.all():
        validate_daily(board)
        if board.date > timezone.localdate():
            assert client.get(f'/api/v1/dailies/{board.pk}/').status_code == 404
            assert client.get(f'/api/v1/dailies/{board.pk}/solutions/').status_code == 404
    available=Daily.objects.filter(date__lte=timezone.localdate()).order_by('date').first()
    if available:
        game=Submission.objects.get(guest_token='release-smoke-progress')
        assert client.get('/api/v1/submissions/me/',{'daily_id':available.pk,'guest_token':game.guest_token}).data['total_points']==500
        response=client.get('/api/v1/players/autocomplete/',{'q':'Faker','role':'mid'})
        assert response.status_code==200 and response.data['results'][0]['nickname']=='Faker'
print('Fresh API and all 31 board checks: OK')
'''


if __name__ == '__main__':
    main()
