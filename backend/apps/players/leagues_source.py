"""Source-backed regional league history from actual dated scoreboard games.

No team-country or residency inference belongs here. An explicit, reviewed
family map groups official league names; all other source labels remain audit
evidence and never turn an international/showmatch appearance into LEC/LCS.
"""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import time
import unicodedata

import requests

from .leaguepedia_source import CargoExport, EXPORT_URL, SourceError, chunks, sql_string

SCOPE = 'leaguepedia_dated_league_appearances'
API_URL = 'https://lol.fandom.com/api.php'
# MediaWiki's explicit redirects, retained in the source snapshot, prove these
# historical labels. They are not country/team-derived spelling guesses.
CATALOGUE_ALIASES = {
    'OGN': ('League of Legends Champions Korea', 'LoL Champions Korea'),
    'SEA Tour': ('League of Legends SEA Tour', 'League of Legends SEA Tour'),
}
FAMILIES = {
    'LoL The Champions': 'LCK', 'LoL Champions Korea': 'LCK',
    'Tencent LoL Pro League': 'LPL',
    'Europe League Championship Series': 'LEC', 'LoL EMEA Championship': 'LEC',
    'League of Legends European Championship': 'LEC',
    'North America League Championship Series': 'LCS', 'League of Legends Championship Series': 'LCS',
    'LoL Master Series': 'LMS', 'Pacific Championship Series': 'PCS',
    'League of Legends Championship Pacific': 'LCP', 'Pacific Challengers League': 'PCL',
    'Garena Premier League': 'GPL', 'League of Legends SEA Tour': 'LST',
    'Oceanic Pro League': 'OPL', 'LoL Circuit Oceania': 'LCO',
    'Vietnam Championship Series': 'VCS', 'LoL Japan League': 'LJL',
    'Turkish Championship League': 'TCL', 'Circuit Brazilian League of Legends': 'CBLOL',
    'Liga Latinoamerica': 'LLA', 'Liga Latinoamérica': 'LLA',
    'Liga Latinoamérica Norte': 'LLN', 'Copa Latinoamérica Sur': 'CLS',
    'LoL Continental League': 'LCL',
    'League of Legends Championship of The Americas': 'LTA',
    'League of Legends Championship of The Americas North': 'LTA',
    'League of Legends Championship of The Americas South': 'LTA',
    'LCP Wildcard League': 'LCP Wildcard',
}


def _text(value):
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(str(value or ''))).split())


def _key(value):
    return _text(value).replace('_', ' ').casefold()


def _stamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as error:
        raise SourceError('League source needs a timezone-aware as_of timestamp') from error


def _targets(records):
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise SourceError('League targets must be a list of player records')
    pages = {}
    for record in records:
        attributes = record.get('attributes') or {}
        if attributes.get('worlds_verified') is not True:
            continue
        page, slug = _text(attributes.get('leaguepedia_page')), record.get('slug')
        if not page or not isinstance(slug, str) or not slug or _key(page) in pages:
            raise SourceError('League targets need unique canonical pages and persistent slugs')
        pages[_key(page)] = (page, slug)
    if not pages or len({slug for _page, slug in pages.values()}) != len(pages):
        raise SourceError('League targets need unique, nonempty verified identities')
    return pages


def _count(value, label):
    if type(value) is not int or value < 0:
        raise SourceError(f'{label}: expected a nonnegative integer')
    return value


def _indexed_totals(rows, pages):
    totals = {}
    for row in rows:
        key = _key(row.get('page'))
        if key not in pages or key in totals:
            raise SourceError('Unknown or duplicate independent league totals')
        counts = {field: _count(row.get(field), field)
                  for field in ('games', 'invalid_game_rows', 'invalid_event_rows')}
        if counts['games'] <= 0 or counts['invalid_game_rows'] or counts['invalid_event_rows']:
            raise SourceError(f'{pages[key][0]}: incomplete dated league game identities')
        totals[key] = counts
    if set(totals) != set(pages):
        raise SourceError('Independent league totals do not cover every target')
    return totals


def _fetch_alias_source(client):
    params = {'action': 'query', 'format': 'json', 'redirects': 1, 'titles': '|'.join(CATALOGUE_ALIASES)}
    path = client.cache_dir / 'league-alias-source.json'
    if path.exists():
        proof = json.loads(path.read_text(encoding='utf-8'))
    else:
        time.sleep(max(0, client.interval - (time.monotonic() - client.last_request)))
        client.last_request = time.monotonic()
        try:
            response = client.session.get(API_URL, params=params, timeout=60)
            if response.status_code == 429:
                raise SourceError('Leaguepedia rate limit while reading league redirects')
            response.raise_for_status()
            proof = {'source_url': API_URL, 'params': params, 'response': response.json()}
        except (requests.RequestException, ValueError) as error:
            raise SourceError(f'Could not read official league redirects: {error}') from error
        path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding='utf-8')
    client.manifest.append({'api_url': API_URL, 'params': proof['params'],
        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return proof


def build_leagues_overlay(snapshot, records):
    """Validate independent aggregate coverage and return a separate overlay."""
    if not isinstance(snapshot, dict) or snapshot.get('source') != 'Leaguepedia' or snapshot.get('scope') != SCOPE:
        raise SourceError('Unrecognized league source/scope')
    cutoff = _stamp(snapshot.get('as_of'))
    pages = _targets(records)
    for field in ('rows', 'totals', 'league_catalogue'):
        if not isinstance(snapshot.get(field), list) or not all(isinstance(row, dict) for row in snapshot[field]):
            raise SourceError(f'{field}: expected a list of objects')
    totals = _indexed_totals(snapshot['totals'], pages)
    catalogue = {}
    for row in snapshot['league_catalogue']:
        label = _text(row.get('league'))
        if not label or label in catalogue:
            raise SourceError('Invalid or duplicate Leaguepedia league catalogue name')
        catalogue[label] = row
    grouped = defaultdict(list)
    seen = set()
    for row in snapshot['rows']:
        key, label = _key(row.get('page')), _text(row.get('league'))
        if key not in pages or (key, label) in seen:
            raise SourceError('Unknown page or duplicated league group')
        seen.add((key, label))
        games = _count(row.get('games'), 'league games')
        if games <= 0:
            raise SourceError('League groups require actual played games')
        if not _text(row.get('example_event')):
            raise SourceError('League group needs a source tournament')
        first, last = _stamp(row.get('first_game')), _stamp(row.get('last_game'))
        if first > last or last >= cutoff:
            raise SourceError('League group dates lie outside the as_of cutoff')
        grouped[key].append({**row, 'league': label or None, 'games': games})
    players, changes, unmapped = [], [], defaultdict(int)
    old_records = {record['slug']: record for record in records}
    for key, (page, slug) in sorted(pages.items()):
        rows = sorted(grouped[key], key=lambda row: _key(row['league']))
        if sum(row['games'] for row in rows) != totals[key]['games']:
            raise SourceError(f'{page}: grouped league games differ from independent totals')
        leagues = set()
        for row in rows:
            label = row['league']
            metadata_label = label
            if label in CATALOGUE_ALIASES:
                target, metadata_label = CATALOGUE_ALIASES[label]
                proof = snapshot.get('league_aliases') or {}
                redirects = proof.get('response', {}).get('query', {}).get('redirects', [])
                if (proof.get('source_url') != API_URL
                        or not any(item.get('from') == label and item.get('to') == target for item in redirects)):
                    raise SourceError(f'{label}: missing official redirect evidence')
            family = FAMILIES.get(metadata_label)
            if family:
                meta = catalogue.get(metadata_label)
                if not meta or _key(meta.get('official')) != 'yes' or _key(meta.get('level')) not in {'primary', 'premier'}:
                    raise SourceError(f'{label}: mapped league lacks official primary metadata')
                leagues.add(family)
            else:
                unmapped[label or '(missing league)'] += row['games']
        leagues = sorted(leagues)
        old = old_records[slug].get('attributes', {}).get('leagues') or []
        if sorted(old) != leagues:
            changes.append({'slug': slug, 'old': old, 'new': leagues})
        players.append({'slug': slug, 'leaguepedia_page': page, 'attributes': {
            'leagues': leagues, 'leagues_meta': {
                'source': 'Leaguepedia', 'scope': SCOPE, 'as_of': snapshot['as_of'], 'complete': True,
                'source_url': EXPORT_URL, 'games': totals[key]['games'],
                'coverage': 'dated_recorded_scoreboards_before_cutoff',
                'league_groups': rows,
            },
        }})
    return {'format_version': 1, 'source': 'Leaguepedia', 'scope': SCOPE, 'as_of': snapshot['as_of'],
            'players': players, 'report': {'players': len(players), 'coverage_verified': True,
                'changed_players': len(changes), 'changes': changes,
                'players_without_regional_league': [row['slug'] for row in players if not row['attributes']['leagues']],
                'unmapped_source_labels': dict(sorted(unmapped.items()))}}


def fetch_leagues_snapshot(records, cache_dir, progress=print, as_of=None, interval=2.0):
    pages = _targets(records)
    as_of = as_of or datetime.now(timezone.utc).isoformat(timespec='seconds')
    cutoff = _stamp(as_of).strftime('%Y-%m-%d %H:%M:%S')
    client = CargoExport(Path(cache_dir) / hashlib.sha256(as_of.encode()).hexdigest()[:16], progress, interval=max(2.0, interval))
    catalogue = client.all('Leagues=L', 'L.League=league,L.Region=region,L.Level=level,L.IsOfficial=official',
                           '1=1', 'L.League ASC')
    totals, groups = [], []
    for index, batch in enumerate(chunks(sorted(page for page, _slug in pages.values()), size=50), 1):
        where = ('PR.OverviewPage IN (' + ','.join(map(sql_string, batch)) + ') AND SP._ID IS NOT NULL'
                 + ' AND SP.DateTime_UTC<' + sql_string(cutoff))
        base = {'tables': 'ScoreboardPlayers=SP,PlayerRedirects=PR', 'join_on': 'PR.AllName=SP.Link', 'where': where}
        fields = ('PR.OverviewPage=page,COUNT(DISTINCT SP.GameId)=games,'
                  "COUNT(CASE WHEN SP.GameId IS NULL OR SP.GameId='' THEN 1 END)=invalid_game_rows,"
                  "COUNT(CASE WHEN SP.OverviewPage IS NULL OR SP.OverviewPage='' THEN 1 END)=invalid_event_rows")
        before = client.query(**base, fields=fields, group_by='PR.OverviewPage', order_by='PR.OverviewPage ASC', limit=500)
        batch_pages = {key: value for key, value in pages.items() if value[0] in batch}
        _indexed_totals(before, batch_pages)
        joined = {**base, 'tables': 'ScoreboardPlayers=SP,PlayerRedirects=PR,Tournaments=T',
                  'join_on': 'PR.AllName=SP.Link,SP.OverviewPage=T.OverviewPage'}
        expected_rows = client.query(**joined,
            fields="PR.OverviewPage=page,COUNT(DISTINCT COALESCE(T.League,''))=groups",
            group_by='PR.OverviewPage', order_by='PR.OverviewPage ASC', limit=500)
        if {_key(row.get('page')) for row in expected_rows} != set(batch_pages):
            raise SourceError('Joined league count is missing canonical targets')
        expected = sum(_count(row.get('groups'), 'league group count') for row in expected_rows)
        batch_groups = []
        while len(batch_groups) < expected:
            rows = client.query(**joined,
                fields='PR.OverviewPage=page,T.League=league,COUNT(DISTINCT SP.GameId)=games,'
                       'MIN(SP.OverviewPage)=example_event,MIN(SP.DateTime_UTC)=first_game,MAX(SP.DateTime_UTC)=last_game',
                group_by='PR.OverviewPage,T.League', order_by='PR.OverviewPage ASC,T.League ASC',
                limit=500, offset=len(batch_groups))
            if not rows or len(rows) > 500:
                raise SourceError('Truncated league groups export')
            for row in rows:
                # Cargo timestamps are declared UTC even when JSON omits a zone.
                for name in ('first_game', 'last_game'):
                    value = row.get(name)
                    if isinstance(value, str) and value:
                        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        row[name] = (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)).isoformat()
            batch_groups.extend(rows)
        if len(batch_groups) != expected:
            raise SourceError('League group count changed during pagination')
        after = client.query(refresh=True, **base, fields=fields, group_by='PR.OverviewPage', order_by='PR.OverviewPage ASC', limit=500)
        if before != after:
            raise SourceError('League source changed while exporting a player batch')
        totals.extend(before)
        groups.extend(batch_groups)
        progress(f'League export batch {index}: {len(totals)}/{len(pages)} players; {len(groups)} groups')
    snapshot = {'format_version': 1, 'source': 'Leaguepedia', 'scope': SCOPE, 'as_of': as_of,
                'league_catalogue': catalogue, 'totals': totals, 'rows': groups, 'manifest': client.manifest}
    if any(row.get('league') in CATALOGUE_ALIASES for row in groups):
        snapshot['league_aliases'] = _fetch_alias_source(client)
    build_leagues_overlay(snapshot, records)
    return snapshot
