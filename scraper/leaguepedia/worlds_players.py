"""
Extract Worlds players S1-S15
"""
from .cargo_api_client import iter_cargo

def fetch_worlds_players(year_start=2011, year_end=2025):
    # ScoreboardPlayers – use OverviewPage LIKE '%World%Championship%'
    # Fields per Cargo table: Name, Link, Team, Role, OverviewPage, DateTime_UTC
    where = f"SP.OverviewPage LIKE '%World%Championship%' AND SP.DateTime_UTC >= '{year_start}-01-01' AND SP.DateTime_UTC <= '{year_end}-12-31'"
    fields = "SP.Link=player, SP.Team=team, SP.Role=role, SP.OverviewPage=tournament, SP.DateTime_UTC=date"
    tables = "ScoreboardPlayers=SP"
    seen = {}
    try:
        for row in iter_cargo(tables, fields, where):
            player = row.get('player') or row.get('Player')
            if not player:
                continue
            # aggregate minimal
            p = seen.setdefault(player, {
                'nickname': player,
                'teams': set(),
                'roles': set(),
                'tournaments': set(),
            })
            if row.get('team'): p['teams'].add(row['team'])
            if row.get('role'): p['roles'].add(str(row['role']).lower())
            if row.get('tournament'): p['tournaments'].add(row['tournament'])
    except Exception as e:
        print(f"[leaguepedia] fetch error (expected in offline dev): {e}")
        return []
    # normalize sets
    result = []
    for v in seen.values():
        v['teams'] = list(v['teams'])
        v['roles'] = list(v['roles'])
        v['tournaments'] = list(v['tournaments'])
        result.append(v)
    return result

if __name__ == "__main__":
    players = fetch_worlds_players()
    print(f"Found {len(players)} players")
