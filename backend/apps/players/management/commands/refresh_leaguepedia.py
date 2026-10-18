"""Refresh verified Worlds data without deleting player identities or answers."""
import json
import gzip
import os
import shutil
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, transaction

from apps.players.leaguepedia_source import fetch_snapshot, prepare_snapshot
from apps.players.worlds_import import build_worlds_players
from apps.players.worlds_achievements import enrich_worlds_achievements


FIXTURE = Path(__file__).resolve().parents[2] / 'fixtures' / 'worlds_players_full.json'


def stage_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                     suffix='.json', delete=False) as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        return Path(stream.name)


class Command(BaseCommand):
    help = 'Validate Leaguepedia against match schedules, write fixtures, optionally update the database'

    def add_arguments(self, parser):
        parser.add_argument('--snapshot', help='Use an offline snapshot instead of downloading')
        parser.add_argument('--save-snapshot', help='Save the fully checked source snapshot')
        parser.add_argument('--cache-dir', default='../tmp/leaguepedia-cache')
        parser.add_argument('--output', default=str(FIXTURE))
        parser.add_argument('--report', default='../docs/worlds-data-audit.json')
        parser.add_argument('--apply', action='store_true', help='Update existing players, preserving IDs')
        parser.add_argument('--dry-run', action='store_true', help='Validate without writing files or database')

    def handle(self, *args, **options):
        staged = []
        backups = {}
        retained_backups = set()
        try:
            progress = lambda message, **_kwargs: self.stdout.write(message)
            if options.get('snapshot'):
                source_path = Path(options['snapshot'])
                raw = gzip.decompress(source_path.read_bytes()) if source_path.suffix == '.gz' else source_path.read_bytes()
                snapshot = json.loads(raw)
            else:
                snapshot = fetch_snapshot(options['cache_dir'], progress)
            snapshot = prepare_snapshot(snapshot, options['cache_dir'], progress,
                                        offline=bool(options.get('snapshot')))
            existing = json.loads(FIXTURE.read_text(encoding='utf-8'))
            records, report = build_worlds_players(snapshot, existing)
            records, achievements = enrich_worlds_achievements(snapshot, records)
            report['achievements'] = achievements
            report['source_manifest'] = snapshot.get('manifest', [])
            report['supplements'] = snapshot.get('supplements', [])
            if not options['dry_run']:
                targets = [(Path(options['output']).resolve(), records),
                           (Path(options['report']).resolve(), report)]
                if options.get('save_snapshot'):
                    targets.append((Path(options['save_snapshot']).resolve(), snapshot))
                for target, data in targets:
                    staged.append((stage_json(target, data), target))
                # Back up every destination before the first database/file
                # mutation. Staging alone cannot undo a later replace failure.
                for _temporary, target in staged:
                    if target in backups:
                        continue
                    backups[target] = None
                    if target.exists():
                        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.worlds-backup-', delete=False) as stream:
                            backup = Path(stream.name)
                        backups[target] = backup
                        shutil.copy2(target, backup)
                replaced = []
                try:
                    with transaction.atomic():
                        if options['apply']:
                            call_command('seed_players', file=str(staged[0][0]), stdout=self.stdout)
                        for temporary, target in staged:
                            os.replace(temporary, target)
                            replaced.append(target)
                except BaseException as error:
                    failures = []
                    for target in reversed(list(dict.fromkeys(replaced))):
                        backup = backups[target]
                        try:
                            if backup is None:
                                target.unlink(missing_ok=True)
                            else:
                                os.replace(backup, target)
                        except OSError as restore_error:
                            if backup is not None:
                                retained_backups.add(backup)
                            failures.append(f'{target}: {restore_error}; backup={backup}')
                    if failures:
                        raise CommandError(f'Leaguepedia refresh failed: {error}; could not restore files: {failures}') from error
                    raise
            self.stdout.write(self.style.SUCCESS(
                f"Verified {report['confirmed_players']} players, {report['games']} played games; "
                f"{report['new_players']} new identities. "
                + ('Validation only.' if options['dry_run'] else 'Saved verified data.')
            ))
        except (OSError, ValueError, KeyError, DatabaseError) as error:
            raise CommandError(f'Leaguepedia refresh rejected: {error}') from error
        finally:
            for temporary, _target in staged:
                temporary.unlink(missing_ok=True)
            for backup in backups.values():
                if backup is not None and backup not in retained_backups:
                    backup.unlink(missing_ok=True)
