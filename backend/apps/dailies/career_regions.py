"""Domestic league identities used by the career-region clue.

Use the dated Leaguepedia scoreboard evidence already shipped with each player.
An international tournament's host country and a player's residency prove no
regional league appearance. League renames stay in the same region.
"""

DOMESTIC_LEAGUES = {
    'KR': ('LoL Champions Korea', 'LoL The Champions', 'OGN', 'Challengers Korea',
           'LCK Challengers League', 'NiceGameTV LoL Battle', 'LCK Academy Series'),
    'CN': ('Tencent LoL Pro League', 'LoL Secondary Pro League', 'LoL Development League'),
    'EU': ('Europe League Championship Series', 'LoL EMEA Championship',
           'League of Legends European Championship', 'Europe Challenger Series',
           'European Masters', 'EMEA Masters', 'La Ligue Française', 'La Ligue Française Division 2',
           'LVP SuperLiga', 'LVP SuperLiga Orange', 'LVP SuperLiga 2nd Division',
           'Northern League of Legends Championship', 'Northern League of Legends Championship 2nd Division',
           'Prime League Pro Division', 'Prime League 1st Division', 'Ultraliga', 'Liga Portuguesa',
           'PG Nationals', 'UK League Championship', 'Esports Balkan League', 'Hitpoint Masters',
           'Hitpoint Challengers', 'Greek Legends League', 'Elite Series: League of Legends'),
    'NA': ('North America League Championship Series', 'League of Legends Championship Series',
           'North America Challenger Series', 'NA Academy League', 'North American Challenger League',
           'North American Challengers League', 'League of Legends Championship of The Americas North'),
    'BR': ('Circuit Brazilian League of Legends', 'Circuit Brazilian League of Legends Academy',
           'Brazilian Challenger Circuit', 'Circuito Desafiante',
           'League of Legends Championship of The Americas South'),
    'PCS': ('LoL Master Series', 'Elite Challenger Series', 'Pacific Championship Series',
            'Pacific Challengers League', 'League of Legends Championship Pacific'),
    'VN': ('Vietnam Championship Series', 'Vietnam Rising Star'),
    'JP': ('LoL Japan League', 'LoL Japan League Challenger Series', 'LJL Academy League'),
    'OCE': ('Oceanic Pro League', 'LoL Circuit Oceania', 'Oceanic Challenger Series'),
    'TR': ('Turkish Championship League', 'Turkish Challenger Series', 'Turkey Academy League',
           'Turkish Promotion League', 'TCL Division 2', 'TCL Season Cup'),
    'CIS': ('LoL Continental League', 'CIS Challenger League', 'SLTV StarSeries'),
    'LATAM': ('Liga Latinoamerica', 'Liga Latinoamérica', 'Liga Latinoamérica Norte',
              'Copa Latinoamérica Norte', 'Copa Latinoamérica Sur', 'Liga Regional Norte', 'Liga Regional Sur'),
}
LEAGUE_REGIONS = {league: region for region, leagues in DOMESTIC_LEAGUES.items() for league in leagues}


def career_regions(attributes):
    meta = attributes.get('leagues_meta')
    if not (isinstance(meta, dict) and meta.get('source') == 'Leaguepedia'
            and meta.get('scope') == 'leaguepedia_dated_league_appearances'
            and meta.get('complete') is True):
        return set()
    rows = meta.get('league_groups')
    if not isinstance(rows, list):
        return set()
    return {LEAGUE_REGIONS[row['league']] for row in rows
            if isinstance(row, dict) and isinstance(row.get('league'), str)
            and row['league'] in LEAGUE_REGIONS
            and type(row.get('games')) is int and row['games'] > 0}
