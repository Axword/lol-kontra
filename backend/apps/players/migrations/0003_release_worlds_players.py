"""Install immutable release data without deleting player identities or progress.

This migration intentionally contains its own validation and merge contract.
Never replace its release file or import current application models/services.
"""
import gzip
import hashlib
import html
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

from django.db import migrations, transaction


RELEASE_FILE = 'worlds_players_2026_10_18_v1.json.gz'
RELEASE_SHA256 = '55a8b147ee8bc3f469d5a8bbb26c580cf909620b7da564eb1f29846a5dbd0f81'
RELEASE_NAME = 'worlds-2026-10-18-v1'
ROLES = {'top', 'jungle', 'mid', 'adc', 'support'}
SCALAR_FIELDS = ('nickname', 'real_name', 'birth_year', 'country_code', 'residency', 'continent',
                 'primary_role', 'secondary_roles', 'is_active', 'worlds_count', 'worlds_titles_count')
ATTRIBUTE_KEYS = {
    'activity_verified', 'coaches', 'country', 'favorite_champions',
    'leaguepedia_country_of_birth', 'leaguepedia_nationality_primary', 'leaguepedia_page',
    'leaguepedia_residency', 'leagues', 'leagues_meta', 'pentakills_worlds',
    'pentakills_worlds_verified', 'portrait_checked_at', 'portrait_description_url',
    'portrait_file', 'portrait_pageid', 'portrait_revid', 'portrait_sha1', 'portrait_source',
    'portrait_status', 'portrait_timestamp', 'portrait_url', 'team_years', 'teams',
    'worlds_achievements', 'worlds_appearances', 'worlds_eliminations', 'worlds_eliminations_meta',
    'worlds_finals', 'worlds_group_escapes', 'worlds_playin', 'worlds_playin_appearances',
    'worlds_roles', 'worlds_semifinals', 'worlds_team_years', 'worlds_teams', 'worlds_titles',
    'worlds_titles_verified', 'worlds_verified', 'top_champions_career',
}
STAT_KEYS = {'worlds', 'career'}


def _identity(value):
    value = str(value or '')
    for _ in range(3):
        value = html.unescape(value)
    return ' '.join(unicodedata.normalize('NFKC', value).replace('_', ' ').split()).casefold()


def _require(ok, message):
    if not ok:
        raise ValueError('Player release rejected: ' + message)


def _complete_stats(stats, scope):
    _require(isinstance(stats, dict) and stats.get('complete') is True
             and stats.get('scope') == scope and stats.get('source') == 'Leaguepedia', 'invalid complete statistics')
    counts = [stats.get(key) for key in ('games', 'wins', 'losses')]
    _require(all(type(value) is int and value >= 0 for value in counts)
             and counts[0] > 0 and counts[0] == counts[1] + counts[2], 'inconsistent game totals')
    champions = stats.get('champions')
    _require(isinstance(champions, list) and bool(champions), 'missing champion breakdown')
    names, games, wins = set(), 0, 0
    for champion in champions:
        _require(isinstance(champion, dict) and isinstance(champion.get('champion'), str)
                 and bool(champion['champion'].strip()), 'invalid champion')
        name = _identity(champion['champion'])
        _require(name not in names, 'duplicate champion')
        names.add(name)
        played, won = champion.get('games'), champion.get('wins')
        _require(type(played) is int and type(won) is int and played > 0 and 0 <= won <= played,
                 'invalid champion totals')
        games, wins = games + played, wins + won
    _require((games, wins) == tuple(counts[:2]), 'champion breakdown differs from game totals')


def validate_release(document):
    _require(isinstance(document, dict) and document.get('schema_version') == 1
             and document.get('release') == RELEASE_NAME, 'wrong release/schema')
    records = document.get('players')
    _require(isinstance(records, list) and len(records) == 882, 'expected 882 player records')
    fields = set(SCALAR_FIELDS) | {'slug', 'attributes', 'career_stats'}
    limits = {'nickname': 64, 'real_name': 128, 'country_code': 3, 'residency': 8,
              'continent': 16, 'primary_role': 16}
    slugs, pages, verified, photos, missing, careers, histories = set(), set(), 0, 0, 0, 0, 0
    for record in records:
        _require(isinstance(record, dict) and set(record) == fields, 'unexpected or missing player fields')
        slug = record['slug']
        _require(isinstance(slug, str) and len(slug) <= 80 and re.fullmatch(r'[a-zA-Z0-9_-]+', slug)
                 and slug.casefold() not in slugs, 'invalid or duplicate natural slug')
        slugs.add(slug.casefold())
        for field, limit in limits.items():
            value = record[field]
            _require((field == 'real_name' and value is None)
                     or (isinstance(value, str) and len(value) <= limit), f'{slug}: invalid {field}')
        _require(bool(record['nickname'].strip()) and record['primary_role'] in ROLES, f'{slug}: invalid nickname/role')
        secondary, born = record['secondary_roles'], record['birth_year']
        _require(isinstance(secondary, list) and all(isinstance(role, str) and role in ROLES for role in secondary), f'{slug}: invalid secondary roles')
        _require(born is None or (type(born) is int and 1900 <= born <= 2100), f'{slug}: invalid birth year')
        # The preserved 144 legacy records encode this flag as integer 0/1.
        active = record['is_active']
        _require(type(active) is bool or (type(active) is int and active in (0, 1)), f'{slug}: invalid activity')
        _require(all(type(record[key]) is int and record[key] >= 0 for key in ('worlds_count', 'worlds_titles_count')),
                 f'{slug}: invalid Worlds counts')
        attrs, stats = record['attributes'], record['career_stats']
        _require(isinstance(attrs, dict) and set(attrs) <= ATTRIBUTE_KEYS and isinstance(stats, dict)
                 and set(stats) <= STAT_KEYS and type(attrs.get('worlds_verified')) is bool, f'{slug}: invalid metadata')
        if attrs['worlds_verified'] is False:
            _require('worlds' not in stats, f'{slug}: excluded player has Worlds statistics')
            continue
        verified += 1
        page = _identity(attrs.get('leaguepedia_page'))
        _require(bool(page) and page not in pages, 'missing or duplicate canonical player page')
        pages.add(page)
        _complete_stats(stats.get('worlds'), 'worlds_including_play_in')
        career = stats.get('career')
        if isinstance(career, dict) and career.get('complete') is True:
            _complete_stats(career, 'leaguepedia_career')
            careers += 1
        else:
            _require(slug == 'jackeylove' and isinstance(career, dict) and career.get('complete') is False
                     and career.get('incomplete_reasons'), f'{slug}: unexpected incomplete career')
        _require(isinstance(attrs.get('worlds_achievements'), dict)
                 and attrs['worlds_achievements'].get('source') == 'Leaguepedia', f'{slug}: missing achievements')
        history = attrs.get('worlds_eliminations_meta')
        _require(isinstance(history, dict) and type(history.get('complete')) is bool
                 and history.get('source') == 'Leaguepedia', f'{slug}: missing stage history')
        histories += history['complete']
        league = attrs.get('leagues_meta')
        _require(isinstance(league, dict) and league.get('complete') is True
                 and league.get('scope') == 'leaguepedia_dated_league_appearances'
                 and isinstance(attrs.get('leagues'), list), f'{slug}: missing league history')
        status = attrs.get('portrait_status')
        if status == 'available':
            parsed = urlsplit(attrs.get('portrait_url', ''))
            _require(attrs.get('portrait_source') == 'Leaguepedia' and parsed.scheme == 'https'
                     and parsed.hostname == 'static.wikia.nocookie.net' and parsed.username is None,
                     f'{slug}: invalid portrait source')
            photos += 1
        else:
            _require(status == 'missing' and not attrs.get('portrait_url'), f'{slug}: unexpected unknown portrait')
            missing += 1
    _require((verified, photos, missing, careers, histories) == (738, 733, 5, 737, 697), 'release coverage mismatch')
    return records


def load_release():
    path = Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / RELEASE_FILE
    payload = gzip.decompress(path.read_bytes())
    _require(hashlib.sha256(payload).hexdigest() == RELEASE_SHA256, 'SHA-256 mismatch')
    return validate_release(json.loads(payload))


def install_release(apps, schema_editor):
    records = load_release()  # Validate everything before any database mutation.
    Player = apps.get_model('players', 'Player')
    alias = schema_editor.connection.alias
    with transaction.atomic(using=alias):
        existing = {player.slug: player for player in Player.objects.using(alias).select_for_update()
                    .filter(slug__in=[record['slug'] for record in records])}
        inserts, updates = [], []
        for record in records:
            old = existing.get(record['slug'])
            old_attrs, old_stats = (old.attributes, old.career_stats) if old else ({}, {})
            _require(isinstance(old_attrs, dict) and isinstance(old_stats, dict), f"{record['slug']}: malformed existing metadata")
            old_page, page = old_attrs.get('leaguepedia_page'), record['attributes'].get('leaguepedia_page')
            _require(not old_page or not page or _identity(old_page) == _identity(page),
                     f"{record['slug']}: existing canonical identity conflicts with release")
            values = {field: record[field] for field in SCALAR_FIELDS}
            values['is_active'] = bool(values['is_active'])
            values['attributes'] = {key: value for key, value in old_attrs.items() if key not in ATTRIBUTE_KEYS}
            values['attributes'].update(record['attributes'])
            values['career_stats'] = {key: value for key, value in old_stats.items() if key not in STAT_KEYS}
            values['career_stats'].update(record['career_stats'])
            if old is None:
                inserts.append(Player(slug=record['slug'], **values))
            else:
                changed = {key: value for key, value in values.items() if getattr(old, key) != value}
                if changed:
                    updates.append((old.pk, changed))
        # Existing identity conflicts above also abort before the first write.
        Player.objects.using(alias).bulk_create(inserts, batch_size=100)
        for pk, values in updates:
            Player.objects.using(alias).filter(pk=pk).update(**values)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [('players', '0002_alter_player_continent_alter_player_country_code_and_more')]
    operations = [migrations.RunPython(install_release, migrations.RunPython.noop)]
