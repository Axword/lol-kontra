"""Worlds achievements derived from checked public results, without database I/O.

Attach the dictionary returned by ``fetch_achievements_source`` to a snapshot as
``achievements_source``. Enrichment is pure; fetching is an explicit operation.
An absent achievement list means unknown. An empty list is written only when
every season in that player's observed career has sufficiently complete proof.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import re
import time
import hashlib
from pathlib import Path

from .leaguepedia_source import CargoExport, SourceError, sql_string, worlds_year
from .worlds_import import _key, _text


FIELDS = ('worlds_titles', 'worlds_finals', 'worlds_semifinals',
          'worlds_group_escapes', 'worlds_playin', 'worlds_playin_appearances')


def _date(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _integer(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r'\d+', value):
        return int(value)
    return None


def _stage(match):
    return str(match.get('tab') or match.get('phase') or match.get('round') or '').casefold().strip()


def _completed(match, cutoff):
    winner = _integer(match.get('winner'))
    scores = [_integer(match.get('score1')), _integer(match.get('score2'))]
    best = _integer(match.get('best_of'))
    start = _date(match.get('date'))
    return (not match.get('nullified') and winner in (1, 2) and best in (1, 3, 5, 7)
            and None not in scores and min(scores) >= 0 and scores[winner - 1] == best // 2 + 1
            and scores[2 - winner] < scores[winner - 1] and start is not None and start <= cutoff)


def fetch_achievements_source(snapshot, cache_dir, progress=print):
    """Fetch scoped schedule/results plus explicit 2011 carry-over evidence.

    Uses public Special:CargoExport, its checked pagination and one request per
    second. MediaWiki revisions provide immutable rule evidence; no cargoquery.
    """
    pages = sorted({row['OverviewPage'] for row in snapshot['tournaments']
                    if worlds_year(row.get('OverviewPage', '')) is not None})
    cutoff = _date(snapshot.get('as_of'))
    if cutoff is None or not pages:
        raise SourceError('A dated, scoped Worlds snapshot is required')
    client = CargoExport(Path(cache_dir) / ('achievements-' + hashlib.sha256(snapshot['as_of'].encode()).hexdigest()[:16]), progress)
    event_filter = 'OverviewPage IN (' + ','.join(map(sql_string, pages)) + ')'
    schedule_fields = (
        'OverviewPage=tournament,MatchId=match_id,Team1=team1,Team2=team2,'
        'Team1Score=score1,Team2Score=score2,Team1Advantage=advantage1,Team2Advantage=advantage2,'
        'Winner=winner,BestOf=best_of,Round=round,Phase=phase,Tab=tab,ShownRound=shown_round,'
        'DateTime_UTC=date,IsNullified=nullified,N_MatchInTab=number'
    )
    schedule = client.all('MatchSchedule', schedule_fields,
                          event_filter + ' AND DateTime_UTC < ' + sql_string(cutoff.strftime('%Y-%m-%d %H:%M:%S')),
                          'OverviewPage ASC,DateTime_UTC ASC,MatchId ASC')
    result_pages = sorted(set(pages) | {page.removesuffix('/Main Event') for page in pages})
    results = client.all('TournamentResults',
                         'OverviewPage=tournament,Team=team,Place=place,Place_Number=place_number,Phase=phase,Date=date,Qualified=qualified',
                         'OverviewPage IN (' + ','.join(map(sql_string, result_pages)) + ')',
                         'OverviewPage ASC,Place_Number ASC,Team ASC')
    season1_games = []
    if 'Season 1 World Championship' in pages:
        season1_games = client.all('MatchScheduleGame',
                                  'GameId=game_id,MatchId=match_id,Blue=blue,Red=red,Winner=winner,FF=ff,Vod=vod',
                                  "OverviewPage='Season 1 World Championship'", 'MatchId ASC,N_GameInMatch ASC')
    time.sleep(max(0, client.interval - (time.monotonic() - client.last_request)))
    response = client.session.get('https://lol.fandom.com/api.php', params={
        'action': 'query', 'prop': 'revisions', 'titles': 'Season 1 World Championship',
        'rvprop': 'content|ids', 'rvslots': 'main', 'format': 'json', 'formatversion': 2,
    }, timeout=30)
    response.raise_for_status()
    try:
        revision = response.json()['query']['pages'][0]['revisions'][0]
        text = revision['slots']['main']['content']
        revid = revision['revid']
    except (ValueError, KeyError, IndexError, TypeError) as error:
        raise SourceError('Cannot verify the published Season 1 rules') from error
    rules = {'page': 'Season 1 World Championship', 'revid': revid,
             'source_url': f'https://lol.fandom.com/wiki/Season_1_World_Championship?oldid={revid}',
             'text': text}
    return {'format_version': 1, 'source': 'Leaguepedia', 'scope': snapshot['scope'],
            'as_of': snapshot['as_of'], 'complete': True, 'schedule': schedule, 'results': results,
            'season1_schedule_games': season1_games, 'season1_rules': rules, 'manifest': client.manifest}


def _redirects(snapshot):
    # Use the importer's MediaWiki identity rules, including case/underscores,
    # while retaining the source page's spelling and its disambiguation suffix.
    canonical_pages = {_key(item.get('page')): _text(item.get('page'))
                       for item in snapshot.get('players', []) if _key(item.get('page'))}
    metadata_pages = set(canonical_pages)
    aliases = {}
    for item in snapshot.get('aliases', []):
        alias, page = _key(item.get('alias')), _key(item.get('page'))
        if alias and page:
            if alias in aliases and aliases[alias] != page:
                raise ValueError(f'Ambiguous player identity: {alias}')
            if alias in metadata_pages and alias != page:
                raise ValueError(f'Alias conflicts with a canonical player page: {alias}')
            aliases[alias] = page
            canonical_pages.setdefault(page, _text(item.get('page')))

    def canonical(name):
        name, seen = _key(name), set()
        while name in aliases and aliases[name] != name:
            if name in seen:
                raise ValueError(f'Cyclic player redirect: {name}')
            seen.add(name)
            name = aliases[name]
        return canonical_pages.get(name, name)

    return canonical


def _games(snapshot, cutoff, pages, canonical):
    raw = defaultdict(list)
    for row in snapshot.get('rows', []):
        raw[str(row.get('game_id', ''))].append(row)
    games, invalid = {}, []
    for game_id, rows in raw.items():
        teams = defaultdict(list)
        players, winners, events, dates = set(), set(), set(), set()
        valid = bool(game_id) and len(rows) == 10
        for row in rows:
            player, team = canonical(row.get('player')), str(row.get('team') or '')
            event, played = row.get('tournament'), _date(row.get('date'))
            win = row.get('win')
            if win in ('Yes', True, 1):
                won = True
            elif win in ('No', False, 0):
                won = False
            else:
                won, valid = None, False
            valid &= bool(player and team and player not in players and event in pages
                          and played is not None and played <= cutoff)
            players.add(player)
            teams[team].append((player, won))
            events.add(event)
            dates.add(played)
            if won:
                winners.add(team)
        valid &= len(events) == 1 and len(dates) == 1 and len(teams) == 2 and len(winners) == 1
        valid &= all(len(members) == 5 and len({won for _, won in members}) == 1 for members in teams.values())
        if not valid:
            invalid.append(game_id)
            continue
        games[game_id] = {'id': game_id, 'event': next(iter(events)), 'date': next(iter(dates)),
                          'teams': teams, 'players': players, 'winner': next(iter(winners))}
    return games, invalid


def _series_games(schedule, games, season1_games):
    """Match old Bracket Stage IDs by teams and actual win sequence, not guesses."""
    groups = defaultdict(list)
    for game in games.values():
        groups[game['id'].rsplit('_', 1)[0]].append(game)
    for group in groups.values():
        group.sort(key=lambda game: (_integer(game['id'].rsplit('_', 1)[-1]) or 0, game['date']))
    calendar_games = defaultdict(list)
    for row in season1_games:
        calendar_games[row.get('match_id')].append(row)
    matched = {}
    used = set()
    for match in schedule:
        key = match.get('match_id')
        if key in groups:
            matched[key] = groups[key]
            used.add(key)
            continue
        if match.get('tournament') != 'Season 1 World Championship' or key not in calendar_games:
            continue
        actual = [row for row in calendar_games[key] if not row.get('ff')]
        actual.sort(key=lambda row: _integer(str(row.get('game_id', '')).rsplit('_', 1)[-1]) or 0)
        wins = [row.get('blue') if _integer(row.get('winner')) == 1 else row.get('red') for row in actual]
        candidates = [(group_id, group) for group_id, group in groups.items()
                      if group_id not in used and group and group[0]['event'] == match['tournament']
                      and set(group[0]['teams']) == {match.get('team1'), match.get('team2')}
                      and [game['winner'] for game in group] == wins]
        if len(candidates) == 1:
            group_id, group = candidates[0]
            matched[key] = group
            used.add(group_id)
    return matched, calendar_games


def enrich_worlds_achievements(snapshot, records):
    """Return copied records and an auditable coverage/achievement report."""
    if snapshot.get('scope') != 'worlds_including_play_in' or _date(snapshot.get('as_of')) is None:
        raise ValueError('A dated Worlds-only snapshot is required')
    cutoff = _date(snapshot['as_of'])
    source = snapshot.get('achievements_source') or {}
    if source.get('as_of') not in (None, snapshot['as_of']):
        raise ValueError('Achievement source and snapshot must share the same as_of')
    canonical = _redirects(snapshot)
    pages = {row['OverviewPage'] for row in snapshot.get('tournaments', [])
             if worlds_year(row.get('OverviewPage', '')) is not None}
    games, invalid = _games(snapshot, cutoff, pages, canonical)
    schedule = [row for row in source.get('schedule', []) if row.get('tournament') in pages]
    matched, calendar = _series_games(schedule, games, source.get('season1_schedule_games', []))
    completed = [row for row in schedule if _completed(row, cutoff)]
    event_games = defaultdict(list)
    event_team_players = defaultdict(set)
    player_years = defaultdict(set)
    for game in games.values():
        event_games[game['event']].append(game)
        year = worlds_year(game['event'])
        for team, members in game['teams'].items():
            for player, _ in members:
                event_team_players[(game['event'], team)].add(player)
                player_years[player].add(year)

    expected, forfeits = Counter(), []
    complete_series = set()
    for match in completed:
        event, key = match['tournament'], match.get('match_id')
        scores = {_team: _integer(match.get(f'score{index}')) for index, _team in enumerate((match.get('team1'), match.get('team2')), 1)}
        carried = Counter()
        if event == 'Season 1 World Championship' and key in calendar:
            for row in calendar[key]:
                if row.get('ff'):
                    winner = row.get('blue') if _integer(row.get('winner')) == 1 else row.get('red')
                    carried[winner] += 1
                    forfeits.append({'game_id': row.get('game_id'), 'match_id': key, 'winner': winner, 'ff': row['ff']})
            count = sum(not row.get('ff') for row in calendar[key])
        else:
            for index, team in enumerate((match.get('team1'), match.get('team2')), 1):
                carried[team] = _integer(match.get(f'advantage{index}')) or 0
            count = sum(scores.values()) - sum(carried.values())
        expected[event] += count
        observed = matched.get(key, [])
        wins = Counter(game['winner'] for game in observed) + carried
        if len(observed) == count and all(wins[team] == score for team, score in scores.items()):
            complete_series.add(key)

    coverage = {event: {'expected': expected[event], 'observed': len(event_games[event]),
                        'complete': bool(source.get('complete')) and expected[event] == len(event_games[event])}
                for event in sorted(pages)}
    facts = {field: defaultdict(set) for field in FIELDS}
    known_years = {field: set() for field in FIELDS}
    main_finals = defaultdict(list)
    for match in completed:
        event, year = match['tournament'], worlds_year(match['tournament'])
        if not event.endswith('/Play-In') and _stage(match) in ('final', 'finals', 'grand final', 'grand finals'):
            main_finals[year].append(match)
        if event.endswith('/Play-In'):
            continue
        stage = _stage(match)
        if stage in ('quarterfinals', 'semifinals', 'final', 'finals', 'grand final', 'grand finals'):
            for team in (match.get('team1'), match.get('team2')):
                members = event_team_players[(event, team)]
                if stage == 'semifinals' or stage in ('final', 'finals', 'grand final', 'grand finals'):
                    for player in members:
                        facts['worlds_semifinals'][player].add(year)
                # Direct knockout seeds did not escape a group they never played.
                grouped = any(team in game['teams'] and re.search(r'_(Group Stage|Day \d+|Round \d+)_', game['id'])
                              for game in event_games[event])
                if grouped:
                    for player in members:
                        facts['worlds_group_escapes'][player].add(year)

    for year, finals in main_finals.items():
        if len(finals) != 1:
            continue
        final = finals[0]
        event, key = final['tournament'], final.get('match_id')
        for game in matched.get(key, []):
            for player in game['players']:
                facts['worlds_finals'][player].add(year)
        if key not in complete_series:
            continue
        winner = final.get(f'team{_integer(final.get("winner"))}')
        for player in event_team_players[(event, winner)]:
            facts['worlds_titles'][player].add(year)
        if source.get('complete'):
            known_years['worlds_titles'].add(year)
            known_years['worlds_finals'].add(year)
        if coverage[event]['complete']:
            semi_matches = [match for match in completed if match['tournament'] == event and _stage(match) == 'semifinals']
            quarter_matches = [match for match in completed if match['tournament'] == event and _stage(match) == 'quarterfinals']
            if len(semi_matches) == 2:
                known_years['worlds_semifinals'].add(year)
            if len(quarter_matches) == 4:
                known_years['worlds_group_escapes'].add(year)
            if year == 2011:
                placements = [row for row in source.get('results', []) if row.get('tournament') == event]
                top4 = {row.get('team') for row in placements if _integer(row.get('place_number')) in (1, 2, 3, 4)}
                if len(top4) == 4:
                    for team in top4:
                        for player in event_team_players[(event, team)]:
                            facts['worlds_semifinals'][player].add(year)
                    known_years['worlds_semifinals'].add(year)
                    known_years['worlds_group_escapes'].add(year)
                    for game in event_games[event]:
                        if '_Bracket Stage_' in game['id']:
                            for player in game['players']:
                                facts['worlds_group_escapes'][player].add(year)

    observed_years = set().union(*player_years.values()) if player_years else set()
    for year in observed_years:
        play_events = [page for page in pages if worlds_year(page) == year and page.endswith('/Play-In')]
        main_events = [page for page in pages if worlds_year(page) == year and not page.endswith('/Play-In')]
        for event in play_events:
            for (page, team), members in list(event_team_players.items()):
                if page != event:
                    continue
                for player in members:
                    facts['worlds_playin_appearances'][player].add(year)
                if any(event_team_players[(main, team)] for main in main_events):
                    for player in members:
                        facts['worlds_playin'][player].add(year)
        if source.get('complete') and all(coverage[page]['complete'] for page in play_events):
            known_years['worlds_playin_appearances'].add(year)
            if not play_events or (main_events and all(coverage[page]['complete'] for page in main_events)
                                  and year in known_years['worlds_titles']):
                known_years['worlds_playin'].add(year)

    result = deepcopy(records)
    enriched = 0
    for record in result:
        attributes = record.setdefault('attributes', {})
        player = canonical(attributes.get('leaguepedia_page'))
        seasons = player_years.get(player, set())
        if not seasons:
            continue
        complete_fields = {}
        for field in FIELDS:
            years = sorted(facts[field].get(player, set()))
            complete = seasons <= known_years[field]
            attributes.pop(field, None)
            if years or complete:
                attributes[field] = years
            complete_fields[field] = complete
        attributes['worlds_titles_verified'] = complete_fields['worlds_titles']
        attributes['worlds_achievements'] = {'source': 'Leaguepedia', 'as_of': snapshot['as_of'],
                                           'complete_fields': complete_fields}
        record['worlds_titles_count'] = len(facts['worlds_titles'].get(player, set()))
        enriched += 1
    report = {'enriched_players': enriched, 'expected_game_counts': dict(expected),
              'source': 'Leaguepedia', 'source_as_of': snapshot['as_of'],
              'source_url': 'https://lol.fandom.com/wiki/Special:CargoExport',
              'rules_source': {key: source.get('season1_rules', {}).get(key)
                               for key in ('page', 'revid', 'source_url')},
              'schedule_coverage': coverage,
              'incomplete_events': [event for event, check in coverage.items() if not check['complete']],
              'missing_series': [match.get('match_id') for match in completed if match.get('match_id') not in complete_series],
              'invalid_games': invalid, 'forfeit_points': forfeits,
              'known_years': {field: sorted(years) for field, years in known_years.items()}}
    return result, report


def achievement_coverage(snapshot):
    """Return source coverage before building player records; never mutates input."""
    return enrich_worlds_achievements(snapshot, [])[1]
