"""Confirmed Worlds elimination stages; ongoing or ambiguous stages stay unknown."""
from collections import Counter, defaultdict
from copy import deepcopy
import re

from .leaguepedia_source import CargoExport, sql_string, worlds_year
from .worlds_achievements import (
    _completed, _date, _games, _integer, _redirects, _stage, achievement_coverage,
)


STAGES = ('play_in', 'group', 'quarterfinal', 'semifinal', 'final')
KNOCKOUT = {'quarterfinals': 'quarterfinal', 'semifinals': 'semifinal',
            'final': 'final', 'finals': 'final', 'grand final': 'final', 'grand finals': 'final'}


def fetch_eliminations_source(snapshot, cache_dir, progress=print):
    """Fetch final placements for exact Play-In pages and their parent Worlds."""
    pages = {row['OverviewPage'] for row in snapshot['tournaments']
             if row.get('OverviewPage', '').endswith('/Play-In')}
    pages |= {page.removesuffix('/Play-In') for page in pages}
    if not pages:
        return {'source': 'Leaguepedia', 'as_of': snapshot['as_of'], 'complete': True,
                'source_url': 'https://lol.fandom.com/wiki/Special:CargoExport',
                'results': [], 'manifest': []}
    client = CargoExport(cache_dir, progress, interval=1.0)
    rows = client.all('TournamentResults',
                      'OverviewPage=tournament,Team=team,Place=place,Place_Number=place_number,Phase=phase,Date=date,Qualified=qualified',
                      'OverviewPage IN (' + ','.join(map(sql_string, sorted(pages))) + ')',
                      'OverviewPage ASC,Place_Number ASC,Team ASC')
    return {'source': 'Leaguepedia', 'as_of': snapshot['as_of'], 'complete': True,
            'source_url': 'https://lol.fandom.com/wiki/Special:CargoExport',
            'results': rows, 'manifest': client.manifest}


def _result_year(page):
    year = worlds_year(page or '')
    if year is not None:
        return year
    parent = re.fullmatch(r'(\d{4}) Season World Championship', page or '')
    return int(parent.group(1)) if parent else None


def _qualified(value):
    return value is True or value == 1 or str(value).casefold() in ('yes', 'true', 'q', 'qualified')


def enrich_worlds_eliminations(snapshot, records):
    """Return copied player records and a coverage report, without writes/network.

    Elimination is a team result for anyone who played for that team that Worlds.
    A single early Play-In loss is not elimination: full main-event completion,
    absence from main, and an official non-qualification placement are required.
    """
    report = achievement_coverage(snapshot)
    cutoff = _date(snapshot['as_of'])
    canonical = _redirects(snapshot)
    pages = {row['OverviewPage'] for row in snapshot['tournaments']
             if worlds_year(row.get('OverviewPage', '')) is not None}
    games, _invalid = _games(snapshot, cutoff, pages, canonical)
    schedule = snapshot.get('achievements_source', {}).get('schedule', [])
    extra = snapshot.get('eliminations_source') or {}
    if extra.get('as_of') not in (None, snapshot['as_of']):
        raise ValueError('Elimination results and snapshot must share as_of')
    if extra and (extra.get('source') != 'Leaguepedia' or extra.get('complete') is not True):
        raise ValueError('A checked Leaguepedia placement export is required')
    placements = list(snapshot.get('achievements_source', {}).get('results', [])) + list(extra.get('results', []))
    placed = set()
    for result in placements:
        year = _result_year(result.get('tournament'))
        date = _date(result.get('date'))
        if (year is not None and result.get('team') and date is not None and date <= cutoff
                and (_integer(result.get('place_number')) or 0) > 0 and not _qualified(result.get('qualified'))):
            placed.add((year, result['team']))

    complete_years = set(report['known_years']['worlds_titles'])
    coverage = report['schedule_coverage']
    missing_series = set(report['missing_series'])
    team_members, player_years, player_teams = defaultdict(set), defaultdict(set), defaultdict(set)
    main_teams, playin_teams, grouped, knockout_teams = defaultdict(set), defaultdict(set), defaultdict(set), defaultdict(set)
    for game in games.values():
        event, year = game['event'], worlds_year(game['event'])
        is_playin = event.endswith('/Play-In')
        for team, members in game['teams'].items():
            (playin_teams if is_playin else main_teams)[year].add(team)
            for player, _won in members:
                team_members[(year, team)].add(player)
                player_years[player].add(year)
                player_teams[(player, year)].add((year, team))
            if not is_playin:
                group_pattern = r'_Group Stage_' if year == 2011 else r'_(Group Stage|Day \d+|Round \d+)_'
                if re.search(group_pattern, game['id']):
                    grouped[year].add(team)
                if '_Bracket Stage_' in game['id']:
                    knockout_teams[year].add(team)

    decisions = defaultdict(set)
    champions, known_team_years = set(), set()
    evidence = []
    for match in schedule:
        event, stage = match.get('tournament'), _stage(match)
        year = worlds_year(event or '')
        if (event not in pages or event.endswith('/Play-In') or year not in complete_years
                or not coverage.get(event, {}).get('complete') or not _completed(match, cutoff)):
            continue
        if stage in KNOCKOUT:
            knockout_teams[year].update((match.get('team1'), match.get('team2')))
        if match.get('match_id') in missing_series or stage not in KNOCKOUT:
            continue
        winner_side = _integer(match.get('winner'))
        winner, loser = match.get(f'team{winner_side}'), match.get(f'team{3 - winner_side}')
        decisions[(year, loser)].add(KNOCKOUT[stage])
        evidence.append({'year': year, 'team': loser, 'stage': KNOCKOUT[stage], 'match_id': match.get('match_id')})
        if KNOCKOUT[stage] == 'final':
            champions.add((year, winner))
            known_team_years.add((year, winner))

    unknown_teams = []
    for year in complete_years:
        main_events = [page for page in pages if worlds_year(page) == year and not page.endswith('/Play-In')]
        if not main_events or not all(coverage.get(page, {}).get('complete') for page in main_events):
            continue
        for team in grouped[year] - knockout_teams[year]:
            decisions[(year, team)].add('group')
            evidence.append({'year': year, 'team': team, 'stage': 'group', 'reason': 'Completed main event; no knockout appearance'})
        play_events = [page for page in pages if worlds_year(page) == year and page.endswith('/Play-In')]
        if all(coverage.get(page, {}).get('complete') for page in play_events):
            for team in playin_teams[year] - main_teams[year]:
                if (year, team) in placed:
                    decisions[(year, team)].add('play_in')
                    evidence.append({'year': year, 'team': team, 'stage': 'play_in',
                                     'reason': 'Completed Play-In and main; official final placement; absent from main'})
                else:
                    unknown_teams.append({'year': year, 'team': team, 'reason': 'No verified eliminated Play-In placement'})

    facts = defaultdict(lambda: {stage: set() for stage in STAGES})
    resolved_teams = set()
    for (year, team), members in team_members.items():
        stages = decisions.get((year, team), set())
        if len(stages) > 1 or ((year, team) in champions and stages):
            unknown_teams.append({'year': year, 'team': team, 'reason': 'Conflicting elimination stages'})
            continue
        if stages:
            stage = next(iter(stages))
            known_team_years.add((year, team))
            for player in members:
                facts[player][stage].add(year)
        if (year, team) in known_team_years:
            resolved_teams.add((year, team))
        elif year in complete_years and team in main_teams[year]:
            unknown_teams.append({'year': year, 'team': team,
                                  'reason': 'Completed event but non-standard knockout stage cannot be mapped safely'})

    known_player_years = defaultdict(set)
    for (player, year), teams in player_teams.items():
        if teams <= resolved_teams:
            known_player_years[player].add(year)

    updated, counts = deepcopy(records), Counter()
    for record in updated:
        attributes = record.setdefault('attributes', {})
        player = canonical(attributes.get('leaguepedia_page'))
        years = player_years.get(player, set())
        if not years:
            continue
        data = {stage: sorted(facts[player][stage]) for stage in STAGES}
        known = known_player_years[player]
        attributes.pop('worlds_eliminations', None)
        if any(data.values()) or years <= known:
            attributes['worlds_eliminations'] = data
        attributes['worlds_eliminations_meta'] = {
            'source': 'Leaguepedia', 'as_of': snapshot['as_of'], 'complete': years <= known,
            'known_years': sorted(years & known), 'unknown_years': sorted(years - known),
        }
        counts['players'] += 1
        counts['complete_players'] += int(years <= known)
        for stage in STAGES:
            counts[stage] += bool(data[stage])
    return updated, {'source': 'Leaguepedia', 'as_of': snapshot['as_of'], 'coverage': dict(counts),
                     'unknown_teams': unknown_teams, 'evidence': evidence,
                     'incomplete_events': report['incomplete_events']}
