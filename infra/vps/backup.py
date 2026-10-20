"""Consistent PostgreSQL dump plus media, encrypted and copied off this VPS."""
import argparse
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import re
import subprocess

from configure import read_env, validate


ROOT = Path('/opt/words-v')
CONFIG = Path('/etc/words-v')
BACKUPS = Path('/var/backups/words-v')


def offsite_env(path):
    values = read_env(path)
    allowed = {'RESTIC_REPOSITORY', 'RESTIC_PASSWORD_FILE', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
               'AWS_DEFAULT_REGION', 'AWS_SESSION_TOKEN'}
    if set(values) - allowed:
        raise ValueError('Unexpected backup configuration key')
    repository = values.get('RESTIC_REPOSITORY', '')
    if not repository.startswith(('s3:https://', 'sftp:', 'rest:https://')):
        raise ValueError('Configure an off-server HTTPS/S3 or SFTP restic repository')
    if values.get('RESTIC_PASSWORD_FILE') != '/etc/words-v/restic-password':
        raise ValueError('Use /etc/words-v/restic-password for the backup encryption key')
    return values


def protected_offsite_env():
    if os.geteuid() != 0:
        raise ValueError('Run with sudo')
    for path in (CONFIG / 'backup.env', CONFIG / 'restic-password'):
        info = path.stat()
        if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o777 != 0o600:
            raise ValueError('Backup configuration must be root-owned, mode 0600')
    return {**os.environ, **offsite_env(CONFIG / 'backup.env')}


def main(release):
    if os.geteuid() != 0:
        raise ValueError('Run backup with sudo')
    release = release.resolve(strict=True)
    if release.parent != ROOT / 'releases' or not re.fullmatch(r'[0-9a-f]{40}', release.name):
        raise ValueError('Backup must use a deployed immutable release')
    validate(read_env(CONFIG / 'app.env'))
    extra = protected_offsite_env()
    for path in (CONFIG / 'app.env', CONFIG / 'backup.env', CONFIG / 'restic-password'):
        info = path.stat()
        if path.is_symlink() or info.st_uid != 0 or info.st_mode & 0o777 != 0o600:
            raise ValueError('Backup configuration must be root-owned, mode 0600')
    env = {**os.environ, **extra, 'RELEASE_SHA': release.name}
    command = ['docker', 'compose', '--project-name', 'words-v', '--env-file', str(CONFIG / 'app.env'),
               '-f', str(release / 'compose.vps.yaml'), '--profile', 'maintenance']
    BACKUPS.mkdir(parents=True, exist_ok=True, mode=0o700)
    with Path('/run/lock/words-v-backup.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        before = set(BACKUPS.glob('worlds-xi-*.dump'))
        subprocess.run(command + ['run', '--rm', '--no-deps', 'backup'], env=env, check=True)
        created = set(BACKUPS.glob('worlds-xi-*.dump')) - before
        if len(created) != 1:
            raise ValueError('Expected exactly one newly completed database dump')
        dump = created.pop()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        media = BACKUPS / f'media-{stamp}.tar'
        subprocess.run(command + ['run', '--rm', '--no-deps', '-e', f'BACKUP_STAMP={stamp}', 'backup-media'], env=env, check=True)
        if not media.is_file():
            raise ValueError('Media backup was not created')
        subprocess.run(['restic', 'backup', '--tag', 'words-v', '--tag', release.name,
                        str(dump), str(media), str(CONFIG)], env=env, check=True)
        print('Database, media and configuration copied to the encrypted off-server repository.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, default=ROOT / 'current')
    args = parser.parse_args()
    try:
        main(args.release)
    except (ValueError, OSError, subprocess.CalledProcessError):
        parser.exit(1, 'Backup failed; no deployment should proceed. Check the protected server logs/configuration.\n')
