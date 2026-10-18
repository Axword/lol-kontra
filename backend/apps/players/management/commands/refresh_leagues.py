"""Save source league history and an overlay, never alter player fixtures or DB."""
import gzip
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.players.leagues_source import build_leagues_overlay, fetch_leagues_snapshot


class Command(BaseCommand):
    help = 'Export actual Leaguepedia league appearances to a separate validated overlay'

    def add_arguments(self, parser):
        parser.add_argument('--input', default=str(Path(__file__).resolve().parents[2] / 'fixtures' / 'worlds_players_full.json'))
        parser.add_argument('--snapshot')
        parser.add_argument('--as-of')
        parser.add_argument('--cache-dir', default='../tmp/leagues-cache')
        parser.add_argument('--output', default='../tmp/leagues-overlay.json')
        parser.add_argument('--save-snapshot')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            source_path = Path(options['input']).resolve()
            records = json.loads(source_path.read_text(encoding='utf-8'))
            targets = [Path(value).resolve() for name in ('output', 'save_snapshot') if (value := options[name])]
            if source_path in targets or len(set(targets)) != len(targets):
                raise ValueError('Overlay/source outputs must be separate from the input and each other')
            if options['snapshot']:
                path = Path(options['snapshot'])
                data = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
                snapshot = json.loads(data)
            else:
                snapshot = fetch_leagues_snapshot(records, options['cache_dir'], as_of=options['as_of'],
                    progress=lambda message, **_kwargs: self.stdout.write(message))
            overlay = build_leagues_overlay(snapshot, records)
            if not options['dry_run']:
                for name, data in [('output', overlay), ('save_snapshot', snapshot)]:
                    if options[name]:
                        path = Path(options[name])
                        path.parent.mkdir(parents=True, exist_ok=True)
                        payload = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                        path.write_bytes(gzip.compress(payload, mtime=0) if path.suffix == '.gz' else payload)
            self.stdout.write(self.style.SUCCESS(
                f"Verified {overlay['report']['players']} league histories; {overlay['report']['changed_players']} changed lists"))
        except (OSError, ValueError, TypeError, KeyError) as error:
            raise CommandError(f'League refresh rejected: {error}') from error
