"""Rebuild only Worlds result history from pinned, offline source files."""
from copy import deepcopy
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.players.models import Player
from apps.players.worlds_achievements import FIELDS, enrich_worlds_achievements
from apps.players.worlds_eliminations import enrich_worlds_eliminations


HISTORY_KEYS = (*FIELDS, 'worlds_titles_verified', 'worlds_achievements',
                'worlds_eliminations', 'worlds_eliminations_meta')


def refresh_records(snapshot, records):
    """Merge a strict history whitelist, retaining unrelated data verbatim."""
    achievements, achievement_report = enrich_worlds_achievements(snapshot, records)
    results, elimination_report = enrich_worlds_eliminations(snapshot, achievements)
    updated, changed = deepcopy(records), 0
    for record, refreshed in zip(updated, results):
        if record.get('attributes', {}).get('worlds_verified') is False:
            continue
        attributes = record.setdefault('attributes', {})
        before = deepcopy(record)
        for key in HISTORY_KEYS:
            if key in refreshed['attributes']:
                attributes[key] = deepcopy(refreshed['attributes'][key])
            else:
                attributes.pop(key, None)
        if 'worlds_titles_count' in refreshed:
            record['worlds_titles_count'] = refreshed['worlds_titles_count']
        changed += record != before
    return updated, {'updated_records': changed, 'achievements': achievement_report,
                     'eliminations': elimination_report}


class Command(BaseCommand):
    help = 'Rebuild Worlds achievements/eliminations from pinned sources; default is a dry run'

    def add_arguments(self, parser):
        fixture_dir = Path(__file__).resolve().parents[2] / 'fixtures'
        task_root = Path(settings.BASE_DIR).parent
        parser.add_argument('--fixture', default=str(fixture_dir / 'worlds_players_full.json'))
        parser.add_argument('--snapshot', default=str(fixture_dir / 'worlds_source_snapshot.json.gz'))
        parser.add_argument('--eliminations-source', default=str(fixture_dir / 'worlds_eliminations_source.json.gz'))
        parser.add_argument('--report', default=str(task_root / 'tmp' / 'worlds-history-refresh-report.json'))
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument('--apply', action='store_true', help='Update only history attributes and title counts in fixture and existing DB rows')
        modes.add_argument('--dry-run', action='store_true', help='Prepare a report without changing players or the canonical fixture (default)')

    def handle(self, *args, **options):
        fixture, report_path = Path(options['fixture']), Path(options['report'])
        inputs = [fixture, Path(options['snapshot']), Path(options['eliminations_source'])]
        if report_path.resolve() in {path.resolve() for path in inputs}:
            raise CommandError('The report must not overwrite a source or player fixture')
        try:
            snapshot = self._load_json(Path(options['snapshot']))
            snapshot['eliminations_source'] = self._load_json(Path(options['eliminations_source']))
            _updated, checks = refresh_records(snapshot, self._load_json(fixture))
            report = self._report(options, snapshot, checks)
            if options['apply']:
                self._apply(fixture, report_path, snapshot, report)
            else:
                self._write_json(report_path, report)
        except CommandError:
            raise
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(
            f"Worlds history: {checks['achievements']['enriched_players']} source players, "
            f"{report['fixture_updated']} fixture updates, {report['database_updated']} DB updates; "
            f"{'applied' if options['apply'] else 'dry run'}"
        ))

    @staticmethod
    def _report(options, snapshot, checks):
        return {'source': 'Leaguepedia', 'as_of': snapshot['as_of'], 'applied': options['apply'],
                'fixture': str(Path(options['fixture']).resolve()),
                'snapshot': str(Path(options['snapshot']).resolve()),
                'eliminations_source': str(Path(options['eliminations_source']).resolve()),
                'attribute_keys': list(HISTORY_KEYS), 'model_fields': ['attributes', 'worlds_titles_count'],
                'fixture_updated': checks['updated_records'], 'database_updated': 0,
                'backup': None, 'achievements': checks['achievements'], 'eliminations': checks['eliminations']}

    def _apply(self, fixture, report_path, snapshot, report):
        original = None
        fixture_replaced = False
        try:
            with transaction.atomic():
                players = list(Player.objects.select_for_update().order_by('id'))
                records = [{'attributes': player.attributes, 'worlds_titles_count': player.worlds_titles_count}
                           for player in players]
                refreshed, _checks = refresh_records(snapshot, records)
                # Use the database row's current metadata, never fixture metadata,
                # when merging into the live database.
                for player, record in zip(players, refreshed):
                    fields = []
                    for key in ('attributes', 'worlds_titles_count'):
                        if getattr(player, key) != record[key]:
                            setattr(player, key, record[key])
                            fields.append(key)
                    if fields:
                        player.save(update_fields=fields)
                        report['database_updated'] += 1

                # Read the fixture again under the transaction, after any prior
                # authorized refresh had a chance to finish its own merge.
                original = fixture.read_bytes()
                updated, checks = refresh_records(snapshot, json.loads(original))
                report['fixture_updated'] = checks['updated_records']
                if checks['updated_records']:
                    directory = Path(settings.BASE_DIR).parent / 'tmp' / 'worlds-history-backups'
                    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
                    backup = directory / f'{fixture.stem}-{stamp}-{uuid4().hex[:8]}.json'
                    self._write_bytes(backup, original)
                    report['backup'] = str(backup.resolve())
                    if fixture.read_bytes() != original:
                        raise CommandError('Player fixture changed during refresh; retry to preserve the newer data')
                    self._write_json(fixture, updated)
                    fixture_replaced = True
                # A failed report write also rolls the database and fixture back.
                self._write_json(report_path, report)
        except Exception:
            if fixture_replaced:
                try:
                    self._write_bytes(fixture, original)
                except OSError as error:
                    raise CommandError(f"Database rolled back; restore fixture from {report['backup']}: {error}") from error
            raise

    @staticmethod
    def _load_json(path):
        payload = path.read_bytes()
        return json.loads(gzip.decompress(payload) if path.suffix == '.gz' else payload)

    @classmethod
    def _write_json(cls, path, value):
        cls._write_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))

    @staticmethod
    def _write_bytes(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
        try:
            temporary.write_bytes(payload)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
