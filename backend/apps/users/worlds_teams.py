"""Worlds 2026 supporter badges, based on the official tournament primer."""

WORLDS_2026_SOURCE_URL = 'https://lolesports.com/en-GB/news/worlds-2026-primer'

_TEAMS = (
    ('al', 'AL', "Anyone's Legend", 'LPL'),
    ('blg', 'BLG', 'Bilibili Gaming', 'LPL'),
    ('tes', 'TES', 'TOP Esports', 'LPL'),
    ('ig', 'IG', 'Invictus Gaming', 'LPL'),
    ('gen', 'GEN', 'Gen.G', 'LCK'),
    ('hle', 'HLE', 'Hanwha Life Esports', 'LCK'),
    ('t1', 'T1', 'T1', 'LCK'),
    ('dk', 'DK', 'Dplus Kia', 'LCK'),
    ('g2', 'G2', 'G2 Esports', 'LEC'),
    ('mkoi', 'MKOI', 'Movistar KOI', 'LEC'),
    ('kc', 'KC', 'Karmine Corp', 'LEC'),
    ('tlaw', 'TLAW', 'Team Liquid Alienware', 'LCS'),
    ('lyon', 'LYON', 'LYON', 'LCS'),
    ('c9', 'C9', 'Cloud9 Kia', 'LCS'),
    ('tsw', 'TSW', 'Team Secret Whales', 'LCP'),
    ('cfo', 'CFO', 'CTBC Flying Oyster', 'LCP'),
    ('mvk', 'MVK', 'MVK Esports', 'LCP'),
    ('los', 'LOS', 'LOS', 'CBLOL'),
    ('fur', 'FUR', 'FURIA', 'CBLOL'),
)

WORLDS_2026_TEAM_IDS = tuple(team[0] for team in _TEAMS)
WORLDS_2026_TEAMS = tuple({
    'id': team_id,
    'code': code,
    'name': name,
    'region': region,
    'logo_url': f'/teams/worlds-2026/{team_id}.png',
} for team_id, code, name, region in _TEAMS)
_TEAMS_BY_ID = {team['id']: team for team in WORLDS_2026_TEAMS}


def supported_team_details(team_id):
    team = _TEAMS_BY_ID.get(team_id)
    return dict(team) if team else None
