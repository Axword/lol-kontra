"""Run with: python -m unittest discover -s infra/vps -p 'test_*.py'."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from configure import create, read_env, validate

ROOT = Path(__file__).resolve().parents[2]


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'app.env'
        self.secret = 'migrated-key-$NOT_AN_ENV_VAR-#=+!*0123456789abcdefghijklm'
        create(self.path, 'game.example.com', 'ops@example.com', django_secret=self.secret)

    def test_migration_preserves_identity_secret_and_creates_distinct_database_credentials(self):
        values = validate(read_env(self.path))
        self.assertEqual(values['DJANGO_SECRET_KEY'], self.secret)
        self.assertNotEqual(values['POSTGRES_PASSWORD'], values['POSTGRES_APP_PASSWORD'])
        self.assertNotEqual(values['POSTGRES_USER'], values['POSTGRES_APP_USER'])
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_existing_configuration_is_never_overwritten(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            create(self.path, 'other.example.com', 'ops@example.com')
        self.assertEqual(self.path.read_bytes(), before)

    def test_empty_migration_secret_never_silently_generates_a_new_identity_key(self):
        with self.assertRaises(ValueError):
            create(self.path.with_name('other.env'), 'game.example.com', 'ops@example.com', django_secret='')
        self.assertFalse(self.path.with_name('other.env').exists())

    def test_rejects_host_injection_and_private_or_invalid_domains(self):
        values = read_env(self.path)
        for domain in ['https://game.example.com', 'example.com/api', '127.0.0.1', 'localhost',
                       'app.local', 'app.invalid', 'example.com\nBAD=1', 'x.example.com;id', '*.example.com']:
            with self.subTest(domain=domain), self.assertRaises(ValueError):
                validate({**values, 'PUBLIC_DOMAIN': domain})

    def test_rejects_dangerous_role_and_database_version_configuration(self):
        values = read_env(self.path)
        for update in [{'POSTGRES_APP_USER': values['POSTGRES_USER']}, {'POSTGRES_DB': 'db;DROP DATABASE x'},
                       {'POSTGRES_MAJOR': '18'}, {'BACKUP_DIR': '/'}, {'DATABASE_URL': 'do-not-load-neon'},
                       {'POSTGRES_APP_PASSWORD': 'short'}]:
            with self.subTest(keys=list(update)), self.assertRaises(ValueError):
                validate({**values, **update})

    def test_parser_never_executes_shell_or_expands_variables(self):
        self.path.write_text("LITERAL='$(touch do-not-create)${PATH}'\n", encoding='utf-8')
        self.assertEqual(read_env(self.path), {'LITERAL': '$(touch do-not-create)${PATH}'})
        self.path.write_text('KEY=one\nKEY=two\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            read_env(self.path)

    def test_cli_requires_explicit_migration_secret_or_new_install_and_hides_secrets(self):
        result = subprocess.run([os.sys.executable, str(ROOT / 'infra/vps/configure.py'), 'create',
                                 '--file', str(self.path), '--domain', 'game.example.com', '--email', 'ops@example.com'],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--django-secret-file', result.stderr)
        self.assertNotIn(self.secret, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which('docker'), 'Docker CLI is required for Compose validation')
    def test_resolved_compose_preserves_literal_secret_and_exposes_only_https_proxy(self):
        # Own generated credentials only. Never render production configuration.
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith(('POSTGRES_', 'DJANGO_', 'PUBLIC_DOMAIN', 'COMPOSE_', 'RELEASE_SHA', 'ACME_', 'BACKUP_DIR'))}
        environment['RELEASE_SHA'] = 'a' * 40
        result = subprocess.run(['docker', 'compose', '--env-file', str(self.path), '-f',
                                 str(ROOT / 'compose.vps.yaml'), '--profile', 'maintenance', 'config', '--format', 'json'],
                                env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, 'Compose configuration rejected (secret-bearing output suppressed)')
        services = json.loads(result.stdout)['services']
        # `config` escapes dollars for a Compose document that can be parsed
        # again. ci-smoke.sh also checks the actual container value by its hash.
        self.assertEqual(services['api']['environment']['DJANGO_SECRET_KEY'], self.secret.replace('$', '$$'))
        exposed = {name: [port['published'] for port in service.get('ports', [])]
                   for name, service in services.items() if service.get('ports')}
        self.assertEqual(exposed, {'caddy': ['80', '443']})
        self.assertEqual(services['frontend']['build']['args']['NEXT_PUBLIC_API_URL'], '/api/v1')
        self.assertEqual(services['frontend']['tmpfs'], ['/tmp', '/app/.next/cache:uid=1001,gid=1001,mode=0755'])
        self.assertNotEqual(services['api']['environment']['POSTGRES_USER'], services['release']['environment']['POSTGRES_USER'])
        self.assertEqual(services['api']['environment']['POSTGRES_PASSWORD'], read_env(self.path)['POSTGRES_APP_PASSWORD'])
        self.assertTrue(json.loads(result.stdout)['networks']['data']['internal'])


if __name__ == '__main__':
    unittest.main()
