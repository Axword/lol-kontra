from django.core.management.base import BaseCommand
from apps.players.models import Player, Team
from django.utils.text import slugify
import random

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

class Command(BaseCommand):
    help = 'Seed sample Worlds players'

    def add_arguments(self, parser):
        parser.add_argument('--sample', action='store_true', help='Load sample 35+ players')
        parser.add_argument('--full', action='store_true', help='Load full Worlds scraped dataset (876 players)')
        parser.add_argument('--file', type=str, help='Path to JSON seed file')
        parser.add_argument('--clear', action='store_true', help='Clear existing players')

    def handle(self, *args, **options):
        if options['clear']:
            Player.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared players'))

        # Try full dataset first
        if options['full'] or options.get('file'):
            path = options.get('file') or self.find_seed_file()
            if path:
                return self.load_from_json(path)

        # fallback sample

        # seed teams
        for slug, name, region, cc in TEAMS_SEED:
            Team.objects.update_or_create(slug=slug, defaults={'name': name, 'region': region, 'country_code': cc})

        count = 0
        for nick, real, country, residency, role, worlds, titles in SAMPLE_PLAYERS:
            slug = slugify(nick).lower()
            defaults = {
                'nickname': nick,
                'real_name': real,
                'country_code': country,
                'residency': residency,
                'continent': 'Asia' if residency in ['LCK','LPL','LMS','PCS'] else 'Europe' if residency in ['LEC'] else 'North America' if residency=='LCS' else 'International',
                'primary_role': role,
                'secondary_roles': [],
                'is_active': random.choice([True, True, False]),
                'birth_year': random.randint(1994, 2003),
                'worlds_count': worlds,
                'worlds_titles_count': titles,
                'attributes': {
                    'worlds_appearances': list(range(2020, 2020+worlds)) if worlds>0 else [],
                    'worlds_titles': [2013,2015,2016][:titles],
                    'teams': random.sample(['t1','fnatic','g2','edg','dwg','rng'], k=random.randint(1,3)),
                    'leagues': [residency],
                    'coaches': ['kkoma'] if nick in ['Faker','Bengi','Duke','Bang','Wolf'] else [],
                    'top_champions_career': ['Azir','Ryze','LeBlanc'] if role=='mid' else ['Lee Sin','Graves'] if role=='jungle' else ['Gnar','Jayce'] if role=='top' else ['Jinx','Aphelios'] if role=='adc' else ['Thresh','Rakan'],
                    'country': country,
                },
                'career_stats': {}
            }
            obj, created = Player.objects.update_or_create(slug=slug, defaults=defaults)
            if created:
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded {len(SAMPLE_PLAYERS)} players, {count} new'))

    def find_seed_file(self):
        import os
        candidates = [
            'scraper/data_worlds_enriched.json',
            '/app/scraper/data_worlds_enriched.json',
            'backend/../scraper/data_worlds_enriched.json',
            'data_worlds_enriched.json',
            # django app fixture
            os.path.join(os.path.dirname(__file__), '..', '..', 'fixtures', 'worlds_players_full.json'),
            '/app/apps/players/fixtures/worlds_players_full.json',
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        # fallback to repo root
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'scraper', 'data_worlds_enriched.json'))
        if os.path.exists(root):
            return root
        return None

    def load_from_json(self, path):
        import json, os
        from apps.players.models import Player
        # skip if DB already seeded, unless --clear was used
        if Player.objects.count() > 700:
            self.stdout.write(self.style.WARNING(f'DB already has {Player.objects.count()} players – skipping full import (use --clear to force)'))
            return
        self.stdout.write(f'Loading full dataset from {path} ...')
        if not os.path.exists(path):
            self.stdout.write(self.style.ERROR(f'File not found: {path}'))
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        created = 0
        updated = 0
        from apps.players.models import Player
        for item in data:
            slug = item.get('slug')
            if not slug:
                continue
            defaults = {
                'nickname': item.get('nickname'),
                'real_name': item.get('real_name',''),
                'country_code': item.get('country_code','KR')[:3],
                'residency': item.get('residency','LCK'),
                'continent': item.get('continent','Asia'),
                'primary_role': item.get('primary_role','mid'),
                'secondary_roles': item.get('secondary_roles',[]),
                'birth_year': item.get('birth_year'),
                'is_active': bool(item.get('is_active', True)),
                'worlds_count': item.get('worlds_count',0),
                'worlds_titles_count': item.get('worlds_titles_count',0),
                'attributes': item.get('attributes',{}),
                'career_stats': item.get('career_stats',{}),
            }
            obj, was_created = Player.objects.update_or_create(slug=slug, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Loaded {len(data)} players from JSON – created {created}, updated {updated}'))
        return
