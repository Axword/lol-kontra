"""Positive opponent facts from complete official Worlds maps through 2025.

The 2026 snapshot is not complete for the current tournament. Restrict this
index to completed editions, and make that cutoff part of every clue label.
Player identity comes from canonical Leaguepedia pages, never a nickname.
"""
from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import gzip
import json
from pathlib import Path
import re

from .worlds_import import _boolean, _key, _text, _worlds_year, build_worlds_players


SOURCE_SHA256 = '820f8fd0b56fe03ec60fdbe8a007babafe276ba88a54ab8cd6118e00b36f6221'
RELEASE_FILE = 'worlds_opponents_through_2025_v1.json.gz'
RELEASE_SHA256 = 'd0b7eaaa5e95f490f95df1f5f91f2aa85a6f66f22d06229bedecec140dd49fee'
SCOPE = 'worlds_before_2026'
RELATION_FIELDS = ('teams', 'players', 'won_teams', 'won_players')
TEAM_ALIASES = {
    'sktelecomt1': 't1', 'skt1': 't1', 'skt': 't1', 'sktelecomt1k': 't1', 'sktelecomt12': 't1',
    'damwon': 'dwg', 'damwongaming': 'dwg', 'damwonkia': 'dwg', 'dwgkia': 'dwg',
    'dpluskia': 'dwg', 'dplus': 'dwg',
    'genggaming': 'geng', 'samsunggalaxy': 'ssg', 'samsungwhite': 'ssw', 'samsungblue': 'ssb',
    'g2esports': 'g2', 'edwardgaming': 'edg', 'royalnevergiveup': 'rng',
    'jdgaming': 'jdg', 'invictusgaming': 'ig', 'topesports': 'tes',
    'bilibiligaming': 'blg', 'billibilligaming': 'blg', 'weibogaming': 'wbg',
    'hanwhalifeesports': 'hle', 'ktrolster': 'kt', 'cloud9': 'c9',
    'teamliquid': 'tl', 'teamsolomid': 'tsm', 'teamsololmid': 'tsm', 'tsmftx': 'tsm',
    'madlions': 'mad', 'rogue': 'rge', 'misfitsgaming': 'misfits',
}


def normalize_opponent_team(value):
    if not isinstance(value, str):
        return ''
    token = re.sub(r'[^a-z0-9]+', '', value.strip().casefold())
    return TEAM_ALIASES.get(token, token)


def build_worlds_opponents(snapshot, records, source_sha256=None):
    """Validate source coverage, then derive exact opposite-team map facts."""
    build_worlds_players(snapshot, records)  # Reject incomplete/incoherent maps first.
    by_page = {}
    for record in records:
        attrs = record.get('attributes') or {}
        if attrs.get('worlds_verified') is not True:
            continue
        page = _key(attrs.get('leaguepedia_page'))
        if not page or page in by_page:
            raise ValueError('Worlds opponents require unique canonical identities')
        by_page[page] = record
    aliases = {_key(row['alias']): _key(row['page']) for row in snapshot['aliases']}
    relations = {row['slug']: {field: set() for field in RELATION_FIELDS} for row in by_page.values()}
    games = defaultdict(dict)
    for raw in snapshot['rows']:
        if _worlds_year(_text(raw['tournament'])) >= 2026:
            continue
        page = aliases.get(_key(raw['player']), _key(raw['player']))
        if page not in by_page:
            raise ValueError('Worlds opponent source has an unknown canonical identity')
        slug = by_page[page]['slug']
        games[raw['game_id']][slug] = {
            'team': normalize_opponent_team(raw['team']), 'win': _boolean(raw['win']),
        }
    for game in games.values():
        if len({row['team'] for row in game.values()}) != 2:
            raise ValueError('Distinct source teams collide after normalization')
        for slug, row in game.items():
            for opponent_slug, opponent in game.items():
                if row['team'] == opponent['team']:
                    continue
                relations[slug]['teams'].add(opponent['team'])
                relations[slug]['players'].add(opponent_slug)
                if row['win']:
                    relations[slug]['won_teams'].add(opponent['team'])
                    relations[slug]['won_players'].add(opponent_slug)
    return {
        'schema_version': 1, 'source': 'Leaguepedia', 'scope': SCOPE,
        'complete_through_year': 2025, 'as_of': snapshot['as_of'],
        'source_sha256': source_sha256 or sha256(json.dumps(snapshot, ensure_ascii=False).encode()).hexdigest(),
        'games': len(games),
        'players': [{
            'slug': row['slug'], 'leaguepedia_page': row['attributes']['leaguepedia_page'],
            'relations': {field: sorted(relations[row['slug']][field]) for field in RELATION_FIELDS},
        } for row in sorted(by_page.values(), key=lambda row: row['slug'])],
    }


@lru_cache(maxsize=1)
def load_worlds_opponents():
    payload = gzip.decompress((Path(__file__).resolve().parent / 'fixtures' / 'releases' / RELEASE_FILE).read_bytes())
    if sha256(payload).hexdigest() != RELEASE_SHA256:
        raise ValueError('Worlds opponent evidence checksum mismatch')
    document = json.loads(payload)
    metadata = {key: document[key] for key in ('source', 'scope', 'complete_through_year', 'as_of', 'source_sha256')}
    return {row['slug']: {
        'leaguepedia_page': row['leaguepedia_page'],
        'metadata': {**metadata, 'complete': True, **row['relations']},
    } for row in document['players']}


def with_worlds_opponents(record, relation_index=None):
    entry = (load_worlds_opponents() if relation_index is None else relation_index).get(record.get('slug'))
    attrs = record.get('attributes') or {}
    if (not entry or attrs.get('worlds_verified') is not True
            or _key(attrs.get('leaguepedia_page')) != _key(entry['leaguepedia_page'])):
        return record
    return {**record, 'attributes': {**attrs, 'worlds_opponents': deepcopy(entry['metadata'])}}
