"""
Scraper dla drużyn z Leaguepedia Cargo API.
Pobiera listę drużyn Worlds z informacją o regionie,
mistrzostwach Worlds i statusie aktywnym.
"""
from .cargo_api_client import iter_cargo
from typing import Optional


# Lista drużyn które wygrały Worlds (z roku)
WORLDS_CHAMPIONS = {
    'SK Telecom T1': [2013, 2015, 2016],
    'Samsung Galaxy': [2017],
    'DWG KIA': [2020],
    'Dplus KIA': [2020],
    'Damwon Gaming': [2020],
    'Invictus Gaming': [2018],
    'FunPlus Phoenix': [2019],
    'EDward Gaming': [2021],
    'DRX': [2022],
    'T1': [2023, 2024],
}


def fetch_worlds_teams(year_start: int = 2011, year_end: int = 2025) -> list[dict]:
    """
    Pobiera listę drużyn które wystąpiły na Worlds S1-S15.

    Returns:
        Lista słowników z informacjami o drużynach:
        [
            {
                'slug': 't1',
                'name': 'T1',
                'region': 'LCK',
                'country_code': 'KR',
                'is_active': True,
                'is_worlds_champion': True,
                'worlds_titles_years': [2013, 2015, 2016, 2023, 2024],
                'logo_url': '',
            },
            ...
        ]
    """
    where = (
        f"SP.OverviewPage LIKE '%World%Championship%'"
        f" AND SP.DateTime_UTC >= '{year_start}-01-01'"
        f" AND SP.DateTime_UTC <= '{year_end}-12-31'"
    )
    fields = "SP.Team=team, SP.OverviewPage=tournament, SP.DateTime_UTC=date"
    tables = "ScoreboardPlayers=SP"

    seen = {}
    try:
        for row in iter_cargo(tables, fields, where):
            team_name = row.get('team')
            if not team_name:
                continue
            if team_name not in seen:
                seen[team_name] = {
                    'name': team_name,
                    'tournaments': set(),
                    'years': set(),
                }
            if row.get('tournament'):
                seen[team_name]['tournaments'].add(row['tournament'])
            if row.get('date'):
                try:
                    year = int(str(row['date'])[:4])
                    seen[team_name]['years'].add(year)
                except ValueError:
                    pass
    except Exception as e:
        print(f"[leaguepedia] fetch teams error: {e}")
        return []

    result = []
    for name, data in seen.items():
        slug = name.lower().replace(' ', '-').replace('.', '')

        # Sprawdź czy drużyna jest mistrzem
        titles_years = []
        is_champion = False
        for champ_name, champ_years in WORLDS_CHAMPIONS.items():
            if champ_name.lower() == name.lower():
                is_champion = True
                titles_years = champ_years
                break

        # Określ region na podstawie lat aktywności (heurystyka)
        # W produkcji: pobrać z Cargo TeamRoster.Region
        region = _guess_region(name)

        result.append({
            'slug': slug,
            'name': name,
            'region': region,
            'country_code': _guess_country(region),
            'is_active': max(data['years'], default=0) >= 2023,
            'is_worlds_champion': is_champion,
            'worlds_titles_years': titles_years,
            'logo_url': '',
        })

    return result


def fetch_player_team_roles(year_start: int = 2011, year_end: int = 2025) -> list[dict]:
    """
    Pobiera relacje gracz-drużyna z rolą i okresem czasu z ScoreboardPlayers.

    Returns:
        Lista słowników:
        [
            {
                'player_slug': 'faker',
                'team_slug': 't1',
                'role': 'mid',
                'start_date': '2013-05-01',
                'end_date': '2024-11-01',
            },
            ...
        ]
    """
    where = (
        f"SP.OverviewPage LIKE '%World%Championship%'"
        f" AND SP.DateTime_UTC >= '{year_start}-01-01'"
        f" AND SP.DateTime_UTC <= '{year_end}-12-31'"
    )
    fields = "SP.Link=player, SP.Team=team, SP.Role=role, SP.DateTime_UTC=date"
    tables = "ScoreboardPlayers=SP"

    # Aggregate: per (player, team) -> role, min_date, max_date
    agg = {}
    try:
        for row in iter_cargo(tables, fields, where):
            player = row.get('player')
            team = row.get('team')
            role = row.get('role', '').lower()
            date = row.get('date', '')

            if not player or not team:
                continue

            key = (player, team)
            if key not in agg:
                agg[key] = {
                    'player': player,
                    'team': team,
                    'roles': set(),
                    'dates': [],
                }
            if role:
                agg[key]['roles'].add(role)
            if date:
                agg[key]['dates'].append(str(date)[:10])
    except Exception as e:
        print(f"[leaguepedia] fetch player-team roles error: {e}")
        return []

    # Normalize
    result = []
    for (player, team), data in agg.items():
        player_slug = player.lower().replace(' ', '-')
        team_slug = team.lower().replace(' ', '-').replace('.', '')

        # Wybierz najczęstszą rolę
        role = _most_common_role(data['roles'])

        dates = sorted(d for d in data['dates'] if d)
        start = dates[0] if dates else None
        end = dates[-1] if dates else None

        result.append({
            'player_slug': player_slug,
            'team_slug': team_slug,
            'role': role,
            'start_date': start,
            'end_date': end,
        })

    return result


def _most_common_role(roles: set) -> str:
    """Mapuje rolę do standardowej wartości."""
    ROLE_MAP = {
        'top': 'top',
        'jungle': 'jungle', 'jng': 'jungle',
        'mid': 'mid', 'middle': 'mid',
        'adc': 'adc', 'bot': 'adc', 'ad carry': 'adc',
        'support': 'support', 'sup': 'support',
    }
    for r in roles:
        if r in ROLE_MAP:
            return ROLE_MAP[r]
    return ''


def _guess_region(team_name: str) -> str:
    """Heurystyka do określenia regionu na podstawie nazwy drużyny."""
    KR_TEAMS = ['t1', 'sk telecom', 'gen.g', 'drx', 'damwon', 'dplus', 'dwg', 'kt rolster',
                'hanwha', 'samsung', 'rox', 'kz', 'kingzone', 'afreeca', 'kwangdong',
                'nongshim', 'fearx', 'bnk', 'ns']
    CN_TEAMS = ['edward gaming', 'edg', 'rng', 'invictus', 'ig', 'funplus', 'fpx',
                'jd gaming', 'jdg', 'top esports', 'tes', 'bilibili', 'blg',
                'weibo', 'wbg', 'lgd', 'snake', 'suning', 'v5', 'omg', 'lng']
    EU_TEAMS = ['fnatic', 'g2', 'rogue', 'mad lions', 'misfits', 'splyce',
                'sk gaming', 'schalke', 'excel', 'vitality', 'team heretics', 'koi']
    NA_TEAMS = ['cloud9', 'c9', 'tsm', 'team liquid', 'tl', 'flyquest', 'clutch',
                '100 thieves', 'evil geniuses', 'dignitas', 'echo fox', 'immortals']

    name_lower = team_name.lower()

    for keyword in KR_TEAMS:
        if keyword in name_lower:
            return 'LCK'
    for keyword in CN_TEAMS:
        if keyword in name_lower:
            return 'LPL'
    for keyword in EU_TEAMS:
        if keyword in name_lower:
            return 'LEC'
    for keyword in NA_TEAMS:
        if keyword in name_lower:
            return 'LCS'

    return ''


def _guess_country(region: str) -> str:
    """Mapuje region na country_code."""
    mapping = {
        'LCK': 'KR', 'LPL': 'CN', 'LEC': '', 'LCS': 'US',
        'PCS': 'TW', 'CBLOL': 'BR', 'LJL': 'JP', 'VCS': 'VN',
    }
    return mapping.get(region, '')


if __name__ == "__main__":
    teams = fetch_worlds_teams()
    print(f"Found {len(teams)} teams")
    for t in teams[:10]:
        print(f"  {t['name']} ({t['region']}) champion={t['is_worlds_champion']}")
