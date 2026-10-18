"""Public Leaguepedia Cargo export with explicit scope and checked pagination."""
from __future__ import annotations

import hashlib
import json
import re
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import requests

EXPORT_URL = 'https://lol.fandom.com/wiki/Special:CargoExport'


class SourceError(ValueError):
    pass


def sql_string(value):
    return "'" + str(value).replace('\\', '\\\\').replace("'", "''") + "'"


def worlds_year(page):
    early = re.fullmatch(r'Season ([123]) World Championship', page)
    if early:
        return 2010 + int(early.group(1))
    match = re.fullmatch(r'(\d{4}) Season World Championship(?:/(Main Event|Play-In))?', page)
    if not match:
        return None
    year, stage = int(match.group(1)), match.group(2)
    if 2014 <= year <= 2016 and stage is None:
        return year
    if year >= 2017 and stage in ('Main Event', 'Play-In'):
        return year
    return None


class CargoExport:
    def __init__(self, cache_dir, progress=print, interval=1.0):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.progress = progress
        self.interval = interval
        self.last_request = 0.0
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'WorldsXIData/1.0 (public esports statistics; local development)'
        self.manifest = []

    def query(self, refresh=False, **params):
        params = {**params, 'format': 'json'}
        key = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
        # A run's explicit as_of filter makes cached pages reproducible.
        target = self.cache_dir / f'{key}.json'
        if target.exists() and not refresh:
            payload = json.loads(target.read_text(encoding='utf-8'))
        else:
            for attempt in range(3):
                time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
                self.last_request = time.monotonic()
                try:
                    response = self.session.get(EXPORT_URL, params=params, timeout=60)
                    if response.status_code == 429:
                        raise SourceError(f'Leaguepedia rate limit; retry after {response.headers.get("Retry-After", "later")}')
                    response.raise_for_status()
                    payload = response.json()
                except SourceError:
                    raise
                except (requests.RequestException, ValueError) as error:
                    if attempt == 2:
                        raise SourceError(f'Leaguepedia export failed: {error}') from error
                    self.progress(f'Export retry {attempt + 1}/2', flush=True)
                    time.sleep(5 * (attempt + 1))
                    continue
                if isinstance(payload, dict) and payload.get('error'):
                    raise SourceError(f'Leaguepedia error: {payload["error"]}')
                if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
                    raise SourceError('Leaguepedia returned no valid row list')
                target.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
                break
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise SourceError('Invalid cached export')
        self.manifest.append({'params': params, 'rows': len(payload), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
        return payload

    def all(self, tables, fields, where, order_by, limit=500):
        count = self.query(tables=tables, fields='COUNT(*)=n', where=where, limit=1)
        if len(count) != 1 or type(count[0].get('n')) is not int:
            raise SourceError(f'Cannot verify row count for {tables}')
        expected = count[0]['n']
        rows = []
        while len(rows) < expected:
            batch = self.query(tables=tables, fields=fields, where=where, order_by=order_by, limit=limit, offset=len(rows))
            if not batch or len(batch) > limit:
                raise SourceError(f'Truncated export: {tables} {len(rows)}/{expected}')
            rows.extend(batch)
            self.progress(f'{tables}: {len(rows)}/{expected}', flush=True)
        if len(rows) != expected:
            raise SourceError(f'Row count changed during export: {tables}')
        final_count = self.query(refresh=True, tables=tables, fields='COUNT(*)=n', where=where, limit=1)
        if final_count != count:
            raise SourceError(f'Source changed during export: {tables}')
        return rows


def chunks(values, size=100):
    values = sorted(set(values))
    for offset in range(0, len(values), size):
        yield values[offset:offset + size]


def validate_worlds_catalogue(tournaments, cutoff):
    expected = {'Season 1 World Championship', 'Season 2 World Championship', 'Season 3 World Championship'}
    expected.update(f'{year} Season World Championship' for year in range(2014, min(2017, cutoff.year + 1)))
    expected.update(f'{year} Season World Championship/{stage}'
                    for year in range(2017, cutoff.year + 1) for stage in ('Main Event', 'Play-In'))
    actual = {row.get('OverviewPage') for row in tournaments}
    missing = expected - actual
    if missing:
        raise SourceError('Incomplete Worlds tournament catalogue: ' + ', '.join(sorted(missing)))


def fetch_snapshot(cache_dir, progress=print, as_of=None):
    as_of = as_of or datetime.now(timezone.utc).isoformat(timespec='seconds')
    cutoff = datetime.fromisoformat(as_of).astimezone(timezone.utc)
    cutoff_sql = cutoff.strftime('%Y-%m-%d %H:%M:%S')
    client = CargoExport(Path(cache_dir) / hashlib.sha256(as_of.encode()).hexdigest()[:16], progress)
    tournaments = client.all('Tournaments', 'OverviewPage,Name,StandardName,Year,BasePage,IsQualifier,IsOfficial',
                             "OverviewPage LIKE '%World%Championship%'", 'OverviewPage ASC')
    tournaments = [row for row in tournaments if (year := worlds_year(row.get('OverviewPage', ''))) and year <= cutoff.year]
    pages = [row['OverviewPage'] for row in tournaments]
    validate_worlds_catalogue(tournaments, cutoff)
    where = 'SP.OverviewPage IN (' + ','.join(map(sql_string, pages)) + ') AND SP.DateTime_UTC < ' + sql_string(cutoff_sql)
    fields = ('SP.Link=player,SP.Champion=champion,SP.PlayerWin=win,SP.GameId=game_id,SP.DateTime_UTC=date,'
              'SP.OverviewPage=tournament,SP.Team=team,SP.Role=role,SP.IngameRole=ingame_role,SP.Pentakills=pentakills')
    rows = client.all('ScoreboardPlayers=SP', fields, where, 'SP.DateTime_UTC ASC,SP.GameId ASC,SP.Link ASC')
    for row in rows:
        # Cargo JSON may cast a numeric player ID such as "369" to an integer.
        for field in ('player', 'champion', 'game_id', 'tournament', 'team', 'role', 'ingame_role'):
            if row.get(field) is not None:
                row[field] = str(row[field])
    aliases = []
    for batch in chunks(row['player'] for row in rows):
        aliases.extend(client.all('PlayerRedirects=PR', 'PR.AllName=alias,PR.OverviewPage=page',
                                  'PR.AllName IN (' + ','.join(map(sql_string, batch)) + ')', 'PR.AllName ASC'))
    for row in aliases:
        row['alias'], row['page'] = str(row['alias']), str(row['page'])
    canonical = {row['page'] for row in aliases} | ({row['player'] for row in rows} - {row['alias'] for row in aliases})
    players = []
    metadata_fields = ('P.OverviewPage=page,P.ID=id,P.Name=name,P.Country=country,P.NationalityPrimary=nationality_primary,P.Residency=residency,'
                       'P.Role=role,P.Birthdate=birthdate,P.IsRetired=retired,P.FavChamps=favorite_champions')
    for batch in chunks(canonical):
        players.extend(client.all('Players=P', metadata_fields, 'P.OverviewPage IN (' + ','.join(map(sql_string, batch)) + ')', 'P.OverviewPage ASC'))
    for row in players:
        for field in ('page', 'id', 'name', 'country', 'residency', 'role', 'birthdate', 'favorite_champions'):
            if row.get(field) is not None:
                row[field] = str(row[field])
    return {'format_version': 1, 'as_of': as_of, 'scope': 'worlds_including_play_in', 'source': 'Leaguepedia',
            'source_url': EXPORT_URL, 'tournaments': tournaments, 'rows': rows, 'aliases': aliases, 'players': players,
            'manifest': client.manifest}


def add_scoreboard_supplements(snapshot, path=None):
    """Use revision-pinned scoreboards only for games wholly absent from Cargo.

    A subsequent Cargo repair must agree with these results. Partial or
    conflicting overlap fails closed so it cannot silently change statistics.
    """
    path = path or Path(__file__).parent / 'fixtures' / 'worlds_scoreboard_supplements.json'
    supplement = json.loads(Path(path).read_text(encoding='utf-8'))
    result = deepcopy(snapshot)
    cutoff = datetime.fromisoformat(result['as_of']).astimezone(timezone.utc)
    def key(value):
        import unicodedata
        return unicodedata.normalize('NFKC', str(value)).replace('_', ' ').casefold().strip()
    aliases = {key(row['alias']): key(row['page']) for row in result['aliases']}
    def identity(row):
        player = key(row['player'])
        return aliases.get(player, player)
    def facts(row):
        return (identity(row), key(row['champion']), str(row['win']).lower() in ('1', 'true', 'yes'),
                key(row['team']), row['tournament'])
    existing, additions = {}, {}
    for row in result['rows']:
        existing.setdefault(row['game_id'], []).append(row)
    for row in supplement['rows']:
        played = datetime.fromisoformat(row['date']).replace(tzinfo=timezone.utc)
        if played < cutoff:
            additions.setdefault(row['game_id'], []).append(row)
    added = matched = 0
    for game_id, rows in additions.items():
        if game_id in existing:
            if len(existing[game_id]) != 10 or len(rows) != 10 or {facts(row) for row in existing[game_id]} != {facts(row) for row in rows}:
                raise SourceError(f'Scoreboard supplement conflicts with Cargo: {game_id}')
            matched += 1
        else:
            result['rows'].extend(rows)
            added += 1
    result['supplements'] = [{name: supplement[name] for name in
                             ('source', 'source_url', 'source_revid', 'source_sha256', 'schedule_source_revid')} |
                            {'added_games': added, 'matching_cargo_games': matched}]
    return result


def prepare_snapshot(snapshot, cache_dir, progress=print, offline=False):
    from .worlds_achievements import enrich_worlds_achievements, fetch_achievements_source
    validate_worlds_catalogue(snapshot.get('tournaments', []), datetime.fromisoformat(snapshot['as_of']))
    snapshot = add_scoreboard_supplements(snapshot)
    if not snapshot.get('achievements_source'):
        if offline:
            raise SourceError('Offline snapshot requires the independent MatchSchedule source')
        snapshot['achievements_source'] = fetch_achievements_source(snapshot, cache_dir, progress)
    _unused, coverage = enrich_worlds_achievements(snapshot, [])
    if coverage['invalid_games'] or coverage['incomplete_events'] or coverage['missing_series']:
        raise SourceError(f'Independent schedule check failed: {coverage["incomplete_events"]}; '
                          f'missing series: {coverage["missing_series"]}')
    snapshot['expected_game_counts'] = coverage['expected_game_counts']
    return snapshot
