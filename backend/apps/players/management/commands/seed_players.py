from django.core.management.base import BaseCommand
from apps.players.models import Player, Team
from apps.players.career_roles import with_verified_career_roles
from django.utils.text import slugify

SAMPLE_PLAYERS = [
    # nickname, real_name, country, residency, role, worlds, titles
    ("Faker", "Lee Sang-hyeok", "KR", "LCK", "mid", 7, 5),
    ("Chovy", "Jeong Ji-hoon", "KR", "LCK", "mid", 5, 0),
    ("Caps", "Rasmus Winther", "DK", "LEC", "mid", 6, 0),
    ("Rookie", "Song Eui-jin", "KR", "LPL", "mid", 3, 1),
    ("ShowMaker", "Heo Su", "KR", "LCK", "mid", 3, 1),
    ("Canyon", "Kim Geon-bu", "KR", "LCK", "jungle", 4, 1),
    ("Oner", "Moon Hyeon-joon", "KR", "LCK", "jungle", 3, 2),
    ("Jankos", "Marcin Jankowski", "PL", "LEC", "jungle", 7, 0),
    ("Peanut", "Han Wang-ho", "KR", "LCK", "jungle", 5, 0),
    ("Zeus", "Choi Woo-je", "KR", "LCK", "top", 3, 2),
    ("TheShy", "Kang Seung-lok", "KR", "LPL", "top", 3, 1),
    ("BrokenBlade", "Sergen Çelik", "DE", "LEC", "top", 4, 0),
    ("Wunder", "Martin Hansen", "DK", "LEC", "top", 5, 0),
    ("Impact", "Jeong Eon-young", "KR", "LCS", "top", 8, 1),
    ("Gumayusi", "Lee Min-hyeong", "KR", "LCK", "adc", 3, 2),
    ("Ruler", "Park Jae-hyuk", "KR", "LCK", "adc", 6, 1),
    ("Rekkles", "Martin Larsson", "SE", "LEC", "adc", 6, 0),
    ("Uzi", "Jian Zi-Hao", "CN", "LPL", "adc", 5, 0),
    ("Viper", "Park Do-hyeon", "KR", "LPL", "adc", 3, 1),
    ("Deft", "Kim Hyuk-kyu", "KR", "LCK", "adc", 7, 1),
    ("Keria", "Ryu Min-seok", "KR", "LCK", "support", 3, 2),
    ("Mikyx", "Mihael Mehle", "SI", "LEC", "support", 5, 0),
    ("Ming", "Shi Sen-Ming", "CN", "LPL", "support", 4, 0),
    ("CoreJJ", "Jo Yong-in", "KR", "LCS", "support", 5, 1),
    ("BeryL", "Cho Geon-hee", "KR", "LCK", "support", 5, 2),
    # extra variety
    ("Duke", "Lee Ho-seong", "KR", "LCK", "top", 3, 3),
    ("Bengi", "Bae Seong-woong", "KR", "LCK", "jungle", 3, 3),
    ("Bang", "Bae Jun-sik", "KR", "LCK", "adc", 4, 2),
    ("Wolf", "Lee Jae-wan", "KR", "LCK", "support", 4, 2),
    ("Perkz", "Luka Perković", "HR", "LEC", "mid", 7, 0),
    ("Doublelift", "Yiliang Peng", "US", "LCS", "adc", 5, 0),
    ("Bjergsen", "Søren Bjerg", "DK", "LCS", "mid", 5, 0),
    ("xPeke", "Enrique Cedeño", "ES", "LEC", "mid", 3, 1),
    ("sOAZ", "Paul Boyer", "FR", "LEC", "top", 6, 0),
    ("Clearlove", "Ming Kai", "CN", "LPL", "jungle", 5, 0),
    ("Meiko", "Tian Ye", "CN", "LPL", "support", 5, 1),
    ("JackeyLove", "Yu Wen-Bo", "CN", "LPL", "adc", 4, 1),
]

TEAMS_SEED = [
    ('t1', 'T1', 'LCK', 'KR'),
    ('fnatic', 'Fnatic', 'LEC', 'GB'),
    ('g2', 'G2 Esports', 'LEC', 'DE'),
    ('edg', 'EDward Gaming', 'LPL', 'CN'),
    ('dwg', 'DWG KIA', 'LCK', 'KR'),
    ('rng', 'Royal Never Give Up', 'LPL', 'CN'),
]

def _record_quality(item):
    attributes = item.get('attributes') or {}
    return (bool(item.get('real_name')), bool(item.get('birth_year')),
            len(attributes.get('top_champions_career') or []),
            len(attributes.get('teams') or []), len(attributes.get('worlds_appearances') or []))


def _clean_text(value):
    import html
    text = str(value or '')
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return ' '.join(text.split())


class Command(BaseCommand):
    help = 'Import canonical Worlds players without replacing existing player IDs'

    def add_arguments(self, parser):
        parser.add_argument('--sample', action='store_true', help='Load a subset of canonical players')
        parser.add_argument('--full', action='store_true', help='Load and refresh the full canonical dataset')
        parser.add_argument('--file', type=str, help='Path to JSON seed file')
        parser.add_argument('--clear', action='store_true', help='Clear existing players before import')

    def handle(self, *args, **options):
        from django.core.management.base import CommandError
        path = options.get('file') or self.find_seed_file()
        if not path:
            raise CommandError('Player dataset not found')
        return self.load_from_json(path, clear=options['clear'],
                                   sample=options['sample'] or not (options['full'] or options.get('file')))

    def find_seed_file(self):
        from pathlib import Path
        path = Path(__file__).resolve().parents[2] / 'fixtures' / 'worlds_players_full.json'
        return str(path) if path.exists() else None

    def load_from_json(self, path, clear=False, sample=False):
        import json
        from pathlib import Path
        from django.core.management.base import CommandError
        from django.db import transaction

        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise CommandError(f'Cannot read player dataset: {error}') from error
        if not isinstance(data, list) or not all(isinstance(item, dict) and item.get('slug') for item in data):
            raise CommandError('Expected a list of player objects with slugs')

        records = {}
        for item in data:
            slug = item['slug']
            if slug not in records or _record_quality(item) > _record_quality(records[slug]):
                records[slug] = item
        if sample:
            sample_slugs = {slugify(item[0]).lower() for item in SAMPLE_PLAYERS}
            records = {slug: item for slug, item in records.items() if slug in sample_slugs}

        created = updated = 0
        with transaction.atomic():
            if clear:
                Player.objects.all().delete()
            for slug, item in records.items():
                item = with_verified_career_roles(item)
                old = Player.objects.filter(slug=slug).first()
                attributes = dict(old.attributes if old else {})
                attributes.update(item.get('attributes') or {})
                incoming_attributes = item.get('attributes') or {}
                if 'favorite_champions' in incoming_attributes:
                    attributes.pop('top_champions_career', None)
                if incoming_attributes.get('pentakills_worlds_verified') is False:
                    attributes.pop('pentakills_worlds', None)
                # The original scraper emitted [] for every player without ever
                # collecting championship results. Empty is unknown unless verified.
                if not attributes.get('worlds_titles') and not (item.get('attributes') or {}).get('worlds_titles_verified'):
                    if old and old.attributes.get('worlds_titles'):
                        attributes['worlds_titles'] = old.attributes['worlds_titles']
                    else:
                        attributes.pop('worlds_titles', None)
                active = item.get('is_active', True)
                if isinstance(active, str):
                    active = active.strip().lower() in ('true', '1', 'yes')
                appearances = attributes.get('worlds_appearances')
                career_stats = dict(old.career_stats if old else {})
                career_stats.update(item.get('career_stats') or {})
                if attributes.get('worlds_verified') is False:
                    career_stats.pop('worlds', None)
                defaults = {
                    'nickname': _clean_text(item.get('nickname') or slug),
                    'real_name': _clean_text(item.get('real_name')),
                    'country_code': _clean_text(item.get('country_code'))[:3].upper(),
                    'residency': _clean_text(item.get('residency')),
                    'continent': _clean_text(item.get('continent')),
                    'primary_role': item.get('primary_role') or 'mid',
                    'secondary_roles': item.get('secondary_roles') or [],
                    'birth_year': item.get('birth_year'),
                    'is_active': bool(active),
                    'worlds_count': len(set(appearances)) if isinstance(appearances, list) else item.get('worlds_count', 0),
                    'worlds_titles_count': len(set(attributes.get('worlds_titles') or [])) or item.get('worlds_titles_count', 0),
                    'attributes': attributes,
                    'career_stats': career_stats,
                }
                _, was_created = Player.objects.update_or_create(slug=slug, defaults=defaults)
                created += int(was_created)
                updated += int(not was_created)
        self.stdout.write(self.style.SUCCESS(
            f'Imported {len(records)} unique players: created {created}, updated {updated}, '
            f'ignored {len(data) - len({item["slug"] for item in data})} duplicate rows'
        ))
