"""
Normalize raw Leaguepedia + gol.gg into Player schema
"""
from unidecode import unidecode

ROLE_MAP = {
    'top': 'top', 'Top': 'top',
    'jungle': 'jungle', 'jng': 'jungle', 'Jungle': 'jungle',
    'mid': 'mid', 'middle': 'mid', 'Mid': 'mid',
    'adc': 'adc', 'bot': 'adc', 'AD Carry': 'adc',
    'support': 'support', 'sup': 'support', 'Support': 'support',
}

def slugify_nick(nick: str) -> str:
    return unidecode(nick.lower()).replace(' ', '-').replace('_', '-')

def normalize_player(raw: dict) -> dict:
    nick = raw.get('nickname') or raw.get('player') or 'unknown'
    roles = raw.get('roles', [])
    primary_role = 'mid'
    if roles:
        # pick first known
        for r in roles:
            pr = ROLE_MAP.get(r, None)
            if pr:
                primary_role = pr
                break
    return {
        'slug': slugify_nick(nick),
        'nickname': nick,
        'real_name': raw.get('real_name', ''),
        'country_code': raw.get('country', 'KR')[:3].upper(),
        'residency': raw.get('residency', 'LCK'),
        'continent': raw.get('continent', 'Asia'),
        'primary_role': primary_role,
        'secondary_roles': [],
        'birth_year': raw.get('birth_year'),
        'is_active': raw.get('is_active', True),
        'worlds_count': len(raw.get('worlds_appearances', [])),
        'worlds_titles_count': len(raw.get('worlds_titles', [])),
        'attributes': {
            'worlds_appearances': raw.get('worlds_appearances', []),
            'worlds_titles': raw.get('worlds_titles', []),
            'teams': raw.get('teams', []),
            'leagues': raw.get('leagues', []),
            'coaches': raw.get('coaches', []),
            'top_champions_career': raw.get('top_champions_career', []),
        },
        'career_stats': raw.get('career_stats', {}),
    }

def run_etl():
    # In production: fetch from leaguepedia + gol.gg
    # Here: placeholder – use seed_players command instead
    from scraper.leaguepedia.worlds_players import fetch_worlds_players
    raw_players = fetch_worlds_players()
    normalized = [normalize_player(p) for p in raw_players]
    print(f"[etl] normalized {len(normalized)} players")
    # upsert
    try:
        from scraper.etl.upsert import bulk_upsert_players
        bulk_upsert_players(normalized)
    except Exception as e:
        print(f"[etl] upsert skipped (no DB / Django not configured): {e}")
    return normalized
