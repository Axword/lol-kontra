import json
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.players.models import Player
from apps.players.portraits import apply_portraits, fetch_player_portraits


class Command(BaseCommand):
    help = 'Fetch official Leaguepedia portraits; --apply updates only portrait metadata in fixture and DB'

    def add_arguments(self, parser):
        task_root = Path(settings.BASE_DIR).parent
        parser.add_argument('--fixture', default=str(Path(__file__).resolve().parents[2] / 'fixtures' / 'worlds_players_full.json'))
        parser.add_argument('--source', help='Use a saved portrait response without network')
        parser.add_argument('--cache-dir', default=str(task_root / 'tmp' / ('portrait-cache-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))))
        parser.add_argument('--source-output', default=str(task_root / 'tmp' / 'leaguepedia-portrait-source.json'))
        parser.add_argument('--report', default=str(task_root / 'tmp' / 'portrait-report.json'))
        parser.add_argument('--slugs', nargs='+', help='Fetch only these fixture slugs; other metadata is preserved')
        parser.add_argument('--apply', action='store_true', help='Merge portrait keys into canonical fixture and existing players')

    def handle(self, *args, **options):
        fixture = Path(options['fixture'])
        try:
            records = json.loads(fixture.read_text(encoding='utf-8'))
            selected = [record for record in records if not options['slugs'] or record['slug'] in options['slugs']]
            pages = {record.get('attributes', {}).get('leaguepedia_page') for record in selected}
            pages.discard(None)
            if options['source']:
                source = json.loads(Path(options['source']).read_text(encoding='utf-8'))
            else:
                source = fetch_player_portraits(pages, options['cache_dir'],
                                                progress=lambda message, **_: self.stdout.write(message))
                self._write(Path(options['source_output']), source)
            # Read again after fetching; another authorized task may have updated
            # unrelated fields while network requests were in progress.
            latest = json.loads(fixture.read_text(encoding='utf-8'))
            updated, report = apply_portraits(latest, source)
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise CommandError(str(error)) from error
        report.update(requested_pages=len(pages), fixture=str(fixture), applied=options['apply'])
        report['database_updated'] = 0
        if options['apply']:
            original = fixture.read_bytes()
            try:
                with transaction.atomic():
                    for player in Player.objects.select_for_update().order_by('id'):
                        merged, player_report = apply_portraits([{'slug': player.slug, 'attributes': player.attributes}], source)
                        if player_report['updated']:
                            player.attributes = merged[0]['attributes']
                            player.save(update_fields=['attributes'])
                            report['database_updated'] += 1
                    self._write(fixture, updated)
            except Exception:
                fixture.write_bytes(original)
                raise
        self._write(Path(options['report']), report)
        self.stdout.write(self.style.SUCCESS(
            f"Portraits: {report['available']} available, {report['missing']} confirmed missing, "
            f"{report['unknown']} unknown, {report['unmapped']} unmapped; DB updated {report['database_updated']}"
        ))

    @staticmethod
    def _write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + '.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
