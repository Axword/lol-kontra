"""Write a career-only overlay; fixture and database remain untouched."""
import json
import gzip
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.players.career_source import build_career_overlay, fetch_career_snapshot


class Command(BaseCommand):
    help = 'Validate all recorded Leaguepedia career games and save a separate stats overlay'

    def add_arguments(self, parser):
        parser.add_argument('--input', default=str(Path(__file__).resolve().parents[2] / 'fixtures' / 'worlds_players_full.json'))
        parser.add_argument('--snapshot', help='Use an offline career aggregate')
        parser.add_argument('--as-of', help='Reuse the timestamp/cache of an interrupted export')
        parser.add_argument('--save-snapshot', help='Save the aggregate source and query manifest')
        parser.add_argument('--cache-dir', default='../tmp/career-cache')
        parser.add_argument('--output', default='../tmp/career-stats-overlay.json')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--allow-incomplete', action='store_true', help='Explicitly mark conflicting players incomplete; never enable their career conditions')

    def handle(self, *args, **options):
        try:
            records = json.loads(Path(options['input']).read_text(encoding='utf-8'))
            if options['snapshot']:
                path = Path(options['snapshot'])
                raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
                snapshot = json.loads(raw)
            else:
                snapshot = fetch_career_snapshot(records, options['cache_dir'], progress=lambda message, **_kwargs: self.stdout.write(message),
                                                 as_of=options['as_of'], allow_incomplete=options['allow_incomplete'])
            overlay = build_career_overlay(snapshot, records, allow_incomplete=options['allow_incomplete'])
            if not options['dry_run']:
                for path, data in [(options['output'], overlay), (options['save_snapshot'], snapshot)]:
                    if path:
                        target = Path(path)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f"Verified career breakdowns for {overlay['report']['complete_players']}/{overlay['report']['players']} players"))
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise CommandError(f'Career refresh rejected: {error}') from error
