"""Leaguepedia portraits from official infobox metadata and MediaWiki imageinfo."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from .leaguepedia_source import CargoExport, SourceError, chunks, sql_string


API_URL = 'https://lol.fandom.com/api.php'
PORTRAIT_KEYS = ('portrait_url', 'portrait_source', 'portrait_file', 'portrait_pageid',
                 'portrait_revid', 'portrait_timestamp', 'portrait_sha1',
                 'portrait_description_url', 'portrait_checked_at', 'portrait_status')


def _file_title(value):
    if not isinstance(value, str) or not value.strip() or any(char in value for char in '|[]{}<>\n\r'):
        return None
    value = value.strip().removeprefix('File:').replace('_', ' ')
    if value.casefold() == 'unknown infobox image - player.png':
        return None
    return 'File:' + value


def _https(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username and not parsed.password
    except ValueError:
        return False


def parse_imageinfo(payload, requested_files):
    """A failed/omitted response is unknown, never evidence that an image is absent."""
    if not isinstance(payload, dict) or payload.get('error'):
        raise SourceError('MediaWiki returned an imageinfo error')
    query = payload.get('query')
    if not isinstance(query, dict) or not isinstance(query.get('pages'), (list, dict)):
        raise SourceError('MediaWiki returned no image pages')
    redirects = {row['from']: row['to'] for field in ('normalized', 'redirects')
                 for row in query.get(field, []) if row.get('from') and row.get('to')}
    pages = query['pages'].values() if isinstance(query['pages'], dict) else query['pages']
    by_title = {row.get('title'): row for row in pages}
    result = {}
    for requested in requested_files:
        title, seen = requested, set()
        while title in redirects and title not in seen:
            seen.add(title)
            title = redirects[title]
        page = by_title.get(title)
        if page is None:
            result[requested] = {'status': 'unknown', 'file': requested, 'error': 'File omitted from response'}
            continue
        info = next(iter(page.get('imageinfo') or []), None)
        if info is not None:
            url = info.get('thumburl') or info.get('url')
            if not _https(url) or not str(info.get('mime', '')).startswith('image/'):
                result[requested] = {'status': 'unknown', 'file': requested, 'error': 'No valid HTTPS image URL'}
                continue
            result[requested] = {'status': 'available', 'file': title, 'url': url,
                                 'pageid': page.get('pageid'), 'revid': page.get('lastrevid'),
                                 'timestamp': info.get('timestamp'), 'sha1': info.get('sha1'),
                                 'description_url': info.get('descriptionurl')}
        elif 'missing' in page:
            result[requested] = {'status': 'missing', 'file': title}
        else:
            result[requested] = {'status': 'unknown', 'file': title, 'error': 'Image metadata unavailable'}
    return result


def _export_all(client, **params):
    count = client.query(fields='COUNT(*)=n', limit=1,
                         **{key: value for key, value in params.items() if key not in ('fields', 'order_by')})
    if len(count) != 1 or type(count[0].get('n')) is not int:
        raise SourceError('Cannot verify portrait export row count')
    expected, rows = count[0]['n'], []
    while len(rows) < expected:
        batch = client.query(**params, limit=500, offset=len(rows))
        if not batch or len(batch) > 500:
            raise SourceError('Truncated portrait export')
        rows.extend(batch)
    if len(rows) != expected:
        raise SourceError('Portrait export changed during pagination')
    return rows


def _api_imageinfo(client, files):
    params = {'action': 'query', 'prop': 'imageinfo|info', 'titles': '|'.join(files),
              'iiprop': 'url|timestamp|sha1|mime', 'iiurlwidth': 128, 'iilimit': 1,
              'format': 'json', 'formatversion': 2, 'redirects': 1}
    digest = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
    target = client.cache_dir / f'imageinfo-{digest}.json'
    if target.exists():
        payload = json.loads(target.read_text(encoding='utf-8'))
    else:
        time.sleep(max(0, client.interval - (time.monotonic() - client.last_request)))
        client.last_request = time.monotonic()
        response = client.session.get(API_URL, params=params, timeout=30)
        if response.status_code == 429:
            raise SourceError('Leaguepedia imageinfo rate limit; retry later')
        response.raise_for_status()
        payload = response.json()
        parse_imageinfo(payload, files)
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return parse_imageinfo(payload, files)


def fetch_player_portraits(pages, cache_dir, progress=print):
    """Use Players.Image, then the same automatic query as Infobox/Player.

    PlayerImages.IsProfileImage is an explicit suitability flag. Latest profile
    images use COALESCE(SortDate, tournament start/date), as in the wiki module;
    no filename or CDN URL is invented. Cache contents are reproducible; use a
    fresh cache directory for a new refresh.
    """
    client = CargoExport(cache_dir, progress, interval=1.0)
    result, chosen, errors = {}, {}, []
    requested = sorted({str(page) for page in pages if page})
    for batch in chunks(requested, 100):
        try:
            metadata = _export_all(client, tables='Players=P', fields='P.OverviewPage=page,P.Image=image',
                                   where='P.OverviewPage IN (' + ','.join(map(sql_string, batch)) + ')',
                                   order_by='P.OverviewPage ASC')
            by_page = {str(row['page']): row for row in metadata}
            automatic = [page for page in batch if not _file_title(by_page.get(page, {}).get('image'))]
            images = []
            if automatic:
                images = _export_all(
                    client, tables='PlayerRedirects=PR,PlayerImages=PI,Tournaments=T',
                    fields='PR._pageName=page,PI.FileName=image,COALESCE(PI.SortDate,T.DateStartFuzzy,T.Date)=sort_date',
                    join_on='PR.AllName=PI.Link,PI.Tournament=T.OverviewPage',
                    where='PR._pageName IN (' + ','.join(map(sql_string, automatic)) + ')'
                          ' AND PI._pageName IS NOT NULL AND PI.IsProfileImage=1',
                    order_by='PR._pageName ASC,COALESCE(PI.SortDate,T.DateStartFuzzy,T.Date) DESC,PI.FileName ASC',
                )
            for row in images:
                page = str(row.get('page', ''))
                title = _file_title(row.get('image'))
                if title:
                    chosen.setdefault(page, title)
            for page in batch:
                manual = _file_title(by_page.get(page, {}).get('image'))
                if manual:
                    chosen[page] = manual
                if page not in chosen:
                    result[page] = {'status': 'missing' if page in by_page else 'unknown',
                                    'error': None if page in by_page else 'Player absent from source metadata'}
            progress(f'Portrait metadata: {len(result) + len(chosen)}/{len(requested)}', flush=True)
        except Exception as error:
            errors.append({'stage': 'portrait_metadata', 'players': batch, 'error': str(error)})
            for page in batch:
                result[page] = {'status': 'unknown', 'error': str(error)}
                chosen.pop(page, None)
    files = sorted(set(chosen.values()))
    image_data = {}
    for offset in range(0, len(files), 50):
        batch = files[offset:offset + 50]
        try:
            image_data.update(_api_imageinfo(client, batch))
        except Exception as error:
            errors.append({'stage': 'imageinfo', 'files': batch, 'error': str(error)})
            image_data.update({file: {'status': 'unknown', 'file': file, 'error': str(error)} for file in batch})
        progress(f'Portrait files: {min(offset + 50, len(files))}/{len(files)}', flush=True)
    for page, file in chosen.items():
        result[page] = image_data.get(file, {'status': 'unknown', 'error': 'No imageinfo response'})
    return {'source': 'Leaguepedia', 'fetched_at': datetime.now(timezone.utc).isoformat(),
            'source_url': 'https://lol.fandom.com/wiki/Module:Infobox/Player?oldid=4420045',
            'imageinfo_url': API_URL, 'players': result, 'errors': errors, 'manifest': client.manifest}


def apply_portraits(records, source):
    """Merge only portrait keys; unknown results preserve previous metadata."""
    if source.get('source') != 'Leaguepedia' or not isinstance(source.get('players'), dict):
        raise ValueError('A Leaguepedia portrait result is required')
    updated = deepcopy(records)
    report = {'available': 0, 'missing': 0, 'unknown': 0, 'unmapped': 0, 'updated': 0,
              'fetched_at': source.get('fetched_at'), 'errors': source.get('errors', [])}
    for record in updated:
        attributes = record.setdefault('attributes', {})
        page = attributes.get('leaguepedia_page')
        if not page:
            report['unmapped'] += 1
            continue
        portrait = source['players'].get(page, {'status': 'unknown'})
        status = portrait.get('status', 'unknown')
        if status == 'available' and not _https(portrait.get('url')):
            status = 'unknown'
        if status not in ('available', 'missing'):
            report['unknown'] += 1
            continue
        before = {key: attributes[key] for key in PORTRAIT_KEYS if key in attributes}
        if status == 'available' or attributes.get('portrait_source') in (None, 'Leaguepedia'):
            for key in PORTRAIT_KEYS:
                attributes.pop(key, None)
            attributes.update(portrait_source='Leaguepedia', portrait_status=status,
                              portrait_checked_at=source.get('fetched_at'))
            if portrait.get('file'):
                attributes['portrait_file'] = portrait['file']
            if status == 'available':
                attributes['portrait_url'] = portrait['url']
                for field in ('pageid', 'revid', 'timestamp', 'sha1', 'description_url'):
                    if portrait.get(field) is not None:
                        attributes[f'portrait_{field}'] = portrait[field]
        report[status] += 1
        if before != {key: attributes[key] for key in PORTRAIT_KEYS if key in attributes}:
            report['updated'] += 1
    return updated, report
