"""Run recovery operations without sourcing credentials as shell code."""
import argparse
from pathlib import Path
import re
import subprocess

from backup import BACKUPS, protected_offsite_env

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('operation', choices=['init', 'snapshots', 'check', 'restore'])
parser.add_argument('--snapshot')
parser.add_argument('--target', type=Path)
args = parser.parse_args()
try:
    environment = protected_offsite_env()
    command = ['restic', args.operation]
    if args.operation == 'restore':
        if not re.fullmatch(r'[a-f0-9]{8,64}', args.snapshot or '') or args.target is None:
            raise ValueError('Provide a snapshot ID and a new recovery-* directory')
        target = args.target.resolve()
        if target.parent != BACKUPS or not re.fullmatch(r'recovery-[A-Za-z0-9_-]+', target.name) or target.exists():
            raise ValueError('Use a new /var/backups/words-v/recovery-* directory')
        target.mkdir(mode=0o700)
        command += [args.snapshot, '--target', str(target)]
    subprocess.run(command, env=environment, check=True)
except (ValueError, OSError, subprocess.CalledProcessError):
    parser.exit(1, 'Backup operation failed. Review the protected server configuration/logs.\n')
