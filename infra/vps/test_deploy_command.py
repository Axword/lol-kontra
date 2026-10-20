"""Exercise the SSH boundary without sudo privileges or a real deployment."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = (r'C:\Program Files\Git\bin\bash.exe' if os.name == 'nt' else shutil.which('bash'))


def shell_path(path):
    value = str(path).replace('\\', '/')
    return '/' + value[0].lower() + value[2:] if os.name == 'nt' else value


@unittest.skipUnless(BASH and Path(BASH).exists(), 'Bash is required')
class DeploymentCommandTests(unittest.TestCase):
    def run_command(self, original):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / 'sudo'
            fake.write_bytes(b'#!/bin/sh\nprintf "%s\\n" "$@"\n')
            fake.chmod(0o755)
            return subprocess.run([BASH, '--noprofile', '--norc', '-c',
                'export PATH="$1:$PATH"; exec bash "$2"', 'test-deploy', shell_path(directory),
                shell_path(ROOT/'infra/vps/deploy-command.sh')],
                env={**os.environ, 'SSH_ORIGINAL_COMMAND': original}, text=True, capture_output=True)

    def test_permits_only_a_full_lowercase_commit_as_one_argument(self):
        sha = 'a' * 40
        response = self.run_command('deploy ' + sha)
        self.assertEqual(response.returncode, 0, response.stderr)
        self.assertEqual(response.stdout.splitlines(), ['-n', '--', '/usr/local/sbin/words-v-deploy', sha])

    def test_rejects_shell_access_injection_flags_and_unexpected_commands(self):
        for command in ['', 'bash', 'deploy', 'deploy abc', 'deploy ' + 'A' * 40,
                        'deploy ' + 'a' * 40 + '; id', 'deploy ' + 'a' * 40 + ' --rollback',
                        'deploy ' + 'a' * 40 + '\nid', 'sudo /usr/local/sbin/words-v-deploy ' + 'a' * 40]:
            with self.subTest(command=command):
                response = self.run_command(command)
                self.assertEqual(response.returncode, 64, response.stderr)
                self.assertEqual(response.stdout, '')
