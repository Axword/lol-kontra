"""
Bulk upsert players into Django DB
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
# ensure backend is in path
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

try:
    django.setup()
except Exception:
    pass

def bulk_upsert_players(players: list):
    try:
        from apps.players.models import Player
    except Exception as e:
        print(f"[upsert] Django not ready: {e}")
        return 0
    count = 0
    for p in players:
        obj, created = Player.objects.update_or_create(
            slug=p['slug'],
            defaults={
                'nickname': p['nickname'],
                'real_name': p.get('real_name', ''),
                'country_code': p.get('country_code', 'KR'),
                'residency': p.get('residency', 'LCK'),
                'continent': p.get('continent', ''),
                'primary_role': p.get('primary_role', 'mid'),
                'secondary_roles': p.get('secondary_roles', []),
                'is_active': p.get('is_active', True),
                'birth_year': p.get('birth_year'),
                'worlds_count': p.get('worlds_count', 0),
                'worlds_titles_count': p.get('worlds_titles_count', 0),
                'attributes': p.get('attributes', {}),
                'career_stats': p.get('career_stats', {}),
            }
        )
        if created:
            count += 1
    print(f"[upsert] upserted {len(players)} players, {count} new")
    return count
