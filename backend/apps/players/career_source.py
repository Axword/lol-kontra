"""All recorded Leaguepedia scoreboards, independently checked per player.

This scope includes exhibition/All-Star scoreboards present in Leaguepedia. It
does not describe solo queue or assert that every professional match in history
has a scoreboard. Undated recorded games are included, never assigned a date.
"""
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import html
from pathlib import Path
import unicodedata

from apps.dailies.validators import _champion_name
from .leaguepedia_source import CargoExport, EXPORT_URL, SourceError, chunks, sql_string


SCOPE = 'leaguepedia_career'


def _text(value):
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(str(value or ''))).split())


def _key(value):
    return _text(value).replace('_', ' ').casefold()


def _count(value, label):
    if type(value) is not int or value < 0:
        raise SourceError(f'{label}: expected a nonnegative integer')
    return value


def _targets(records):
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise SourceError('Career targets must be a list of player records')
    pages = {}
    for record in records:
        attrs = record.get('attributes') or {}
        if attrs.get('worlds_verified') is not True:
            continue
        page, slug = _text(attrs.get('leaguepedia_page')), record.get('slug')
        if not page or not slug or _key(page) in pages:
            raise SourceError('Career targets need unique canonical pages and persistent slugs')
        pages[_key(page)] = (page, slug)
    if not pages:
        raise SourceError('No verified canonical players to refresh')
    if len({slug for _page, slug in pages.values()}) != len(pages):
        raise SourceError('Career targets contain conflicting player slugs')
    return pages


def _totals(rows, pages, allow_incomplete=False):
    result = {}
    for raw in rows:
        page = _key(raw.get('page'))
        if page not in pages:
            raise SourceError(f'Unexpected canonical career page: {raw.get("page")!r}')
        totals = {field: _count(raw.get(field), f'{pages[page][0]}/{field}')
                  for field in ('games', 'wins', 'losses', 'invalid_game_rows', 'invalid_result_rows', 'future_rows', 'undated_rows')}
        if not allow_incomplete and (totals['games'] <= 0 or totals['wins'] + totals['losses'] != totals['games']
                or any(totals[field] for field in ('invalid_game_rows', 'invalid_result_rows', 'future_rows'))):
            raise SourceError(f'{pages[page][0]}: incomplete or conflicting career results')
        if page in result and result[page] != totals:
            raise SourceError(f'{pages[page][0]}: conflicting independent totals')
        result[page] = totals
    if set(result) != set(pages):
        raise SourceError(f'Missing independent career totals: {sorted(set(pages) - set(result))!r}')
    return result


def build_career_overlay(snapshot, records, allow_incomplete=False):
    """Validate an offline aggregate without changing fixture records or the DB."""
    if not isinstance(snapshot, dict):
        raise SourceError('Career snapshot must be an object')
    if snapshot.get('source') != 'Leaguepedia' or snapshot.get('scope') != SCOPE:
        raise SourceError('Unrecognized career source/scope')
    as_of = snapshot.get('as_of')
    try:
        stamp = datetime.fromisoformat(as_of.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError('timezone required')
    except (AttributeError, TypeError, ValueError) as error:
        raise SourceError('Career source needs a timezone-aware as_of timestamp') from error
    for field in ('aliases', 'totals', 'rows'):
        if not isinstance(snapshot.get(field), list) or not all(isinstance(row, dict) for row in snapshot[field]):
            raise SourceError(f'{field}: expected a list of objects')
    pages = _targets(records)
    aliases = {}
    for row in snapshot['aliases']:
        alias, page = _key(row.get('alias')), _key(row.get('page'))
        if not alias or page not in pages:
            raise SourceError('Unknown/empty canonical career alias')
        if alias in aliases and aliases[alias] != page or alias in pages and alias != page:
            raise SourceError(f'Ambiguous career alias: {row.get("alias")!r}')
        aliases[alias] = page
    totals = _totals(snapshot['totals'], pages, allow_incomplete=allow_incomplete)
    seen = {}
    champions = defaultdict(dict)
    duplicate_rows = 0
    for row in snapshot['rows']:
        page, champion = _key(row.get('page')), _text(row.get('champion'))
        normalized = _champion_name(champion)
        if page not in pages or not normalized:
            raise SourceError('Career group has an unknown page or missing/invalid champion')
        games = _count(row.get('games'), f'{page}/{champion}/games')
        wins = _count(row.get('wins'), f'{page}/{champion}/wins')
        losses = _count(row.get('losses'), f'{page}/{champion}/losses')
        if games <= 0 or wins + losses != games:
            raise SourceError(f'{page}/{champion}: incomplete champion results')
        identity = (page, champion.casefold())
        counts = (games, wins, losses)
        if identity in seen:
            if seen[identity] != counts:
                raise SourceError(f'{page}/{champion}: conflicting duplicate aggregate')
            duplicate_rows += 1
            continue
        seen[identity] = counts
        target = champions[page].setdefault(normalized, {'champion': champion, 'games': 0, 'wins': 0})
        target['games'] += games
        target['wins'] += wins
    overlay, incomplete = [], []
    for key, (page, slug) in sorted(pages.items()):
        groups = sorted(champions[key].values(), key=lambda row: (-row['games'], _champion_name(row['champion'])))
        total = totals[key]
        reasons = []
        if (total['games'] <= 0 or total['wins'] + total['losses'] != total['games']
                or any(total[field] for field in ('invalid_game_rows', 'invalid_result_rows', 'future_rows'))):
            reasons.append('independent_totals_inconsistent')
        if sum(row['games'] for row in groups) != total['games'] or sum(row['wins'] for row in groups) != total['wins']:
            reasons.append('champion_breakdown_differs_from_independent_totals')
        if reasons and not allow_incomplete:
            raise SourceError(f'{page}: career champion totals differ from independent game totals')
        stats = {'complete': not reasons, 'scope': SCOPE, 'source': 'Leaguepedia', 'as_of': as_of,
                 'coverage': 'all_recorded_scoreboards', 'source_url': EXPORT_URL}
        if reasons:
            stats['incomplete_reasons'] = reasons
            incomplete.append({'page': page, 'slug': slug, 'reasons': reasons, 'observed_independent_totals': total})
        else:
            stats.update({field: total[field] for field in ('games', 'wins', 'losses')}, champions=groups)
        overlay.append({'slug': slug, 'leaguepedia_page': page, 'career_stats': {'career': stats}})
    report = {'players': len(overlay), 'complete_players': len(overlay) - len(incomplete), 'incomplete_players': incomplete,
              'source_conflicts': snapshot.get('source_conflicts', []),
              'champion_groups': sum(len(champions[page]) for page in pages),
              'games': sum(row['games'] for row in totals.values()), 'duplicate_aggregate_rows': duplicate_rows,
              'undated_source_rows': sum(row['undated_rows'] for row in totals.values()),
              'coverage_verified': not incomplete, 'coverage': 'all_recorded_scoreboards'}
    return {'format_version': 1, 'as_of': as_of, 'scope': SCOPE, 'source': 'Leaguepedia',
            'players': overlay, 'report': report}


def _aggregate_fields(cutoff_sql):
    return ("COUNT(DISTINCT SP.GameId)=games,"
            "COUNT(DISTINCT CASE WHEN SP.PlayerWin='Yes' THEN SP.GameId END)=wins,"
            "COUNT(DISTINCT CASE WHEN SP.PlayerWin='No' THEN SP.GameId END)=losses,"
            "COUNT(CASE WHEN SP.GameId IS NULL OR SP.GameId='' THEN 1 END)=invalid_game_rows,"
            "COUNT(CASE WHEN SP.PlayerWin IS NULL OR SP.PlayerWin NOT IN ('Yes','No') THEN 1 END)=invalid_result_rows,"
            f"COUNT(CASE WHEN SP.DateTime_UTC>={sql_string(cutoff_sql)} THEN 1 END)=future_rows,"
            "COUNT(CASE WHEN SP.DateTime_UTC IS NULL THEN 1 END)=undated_rows")


def fetch_career_snapshot(records, cache_dir, progress=print, as_of=None, interval=2.0, allow_incomplete=False):
    """Download grouped counts, never the underlying million-row scoreboard."""
    pages = _targets(records)
    as_of = as_of or datetime.now(timezone.utc).isoformat(timespec='seconds')
    cutoff = datetime.fromisoformat(as_of.replace('Z', '+00:00')).astimezone(timezone.utc)
    client = CargoExport(Path(cache_dir) / hashlib.sha256(as_of.encode()).hexdigest()[:16], progress, interval=max(2.0, interval))
    totals, aliases, groups = [], [], []
    fields = _aggregate_fields(cutoff.strftime('%Y-%m-%d %H:%M:%S'))
    for batch in chunks([page for page, _slug in pages.values()], size=50):
        where = 'PR.OverviewPage IN (' + ','.join(map(sql_string, batch)) + ')'
        # Cargo uses an outer join: aliases never used in a game otherwise
        # produce synthetic NULL-scoreboard rows. Exclude those placeholders,
        # while retaining real rows whose GameId/result is invalid for audit.
        query = {'tables': 'ScoreboardPlayers=SP,PlayerRedirects=PR', 'join_on': 'PR.AllName=SP.Link',
                 'where': where + ' AND SP._ID IS NOT NULL'}
        before = client.query(**query, fields='PR.OverviewPage=page,' + fields,
                              group_by='PR.OverviewPage', order_by='PR.OverviewPage ASC', limit=500)
        totals.extend(before)
        offset = 0
        while True:
            rows = client.query(tables='PlayerRedirects=PR', fields='PR.AllName=alias,PR.OverviewPage=page',
                                where=where, group_by='PR.AllName,PR.OverviewPage',
                                order_by='PR.AllName ASC,PR.OverviewPage ASC', limit=500, offset=offset)
            aliases.extend(rows)
            if len(rows) < 500:
                break
            offset += len(rows)
        offset = 0
        while True:
            rows = client.query(**query, fields='PR.OverviewPage=page,SP.Champion=champion,' + fields,
                                group_by='PR.OverviewPage,SP.Champion',
                                order_by='PR.OverviewPage ASC,SP.Champion ASC', limit=500, offset=offset)
            groups.extend(rows)
            if len(rows) < 500:
                break
            offset += len(rows)
        after = client.query(refresh=True, **query, fields='PR.OverviewPage=page,' + fields,
                             group_by='PR.OverviewPage', order_by='PR.OverviewPage ASC', limit=500)
        if before != after:
            raise SourceError('Career source changed while exporting a player batch')
        progress(f'Career export: {len(totals)}/{len(pages)} players; {len(groups)} champion groups')
    snapshot = {'format_version': 1, 'as_of': as_of, 'source': 'Leaguepedia', 'scope': SCOPE,
                'rows': groups, 'totals': totals, 'aliases': aliases, 'manifest': client.manifest}
    build_career_overlay(snapshot, records, allow_incomplete=allow_incomplete)
    return snapshot
