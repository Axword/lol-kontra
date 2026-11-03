"""Install additive, immutable official-map opponent evidence through 2025.

No player identities, scores, saved answers or historical boards are changed.
2026 is deliberately excluded because the source was fetched mid-tournament.
"""
import gzip
from hashlib import sha256
import html
import json
from pathlib import Path
import re
import unicodedata

from django.db import migrations, transaction


RELEASE_FILE = 'worlds_opponents_through_2025_v1.json.gz'
RELEASE_SHA256 = 'd0b7eaaa5e95f490f95df1f5f91f2aa85a6f66f22d06229bedecec140dd49fee'
SOURCE_SHA256 = '820f8fd0b56fe03ec60fdbe8a007babafe276ba88a54ab8cd6118e00b36f6221'
RELATION_FIELDS = {'teams', 'players', 'won_teams', 'won_players'}


def _identity(value):
    for _ in range(3):
        value = html.unescape(str(value or ''))
    return ' '.join(unicodedata.normalize('NFKC', value).replace('_', ' ').split()).casefold()


def _require(value, message):
    if not value:
        raise ValueError('Worlds opponent release rejected: ' + message)


def validate_release(document):
    _require(isinstance(document, dict) and document.get('schema_version') == 1
             and document.get('source') == 'Leaguepedia' and document.get('scope') == 'worlds_before_2026'
             and type(document.get('complete_through_year')) is int and document['complete_through_year'] == 2025
             and document.get('source_sha256') == SOURCE_SHA256
             and document.get('as_of') == '2026-10-19T07:18:52+00:00', 'invalid source or coverage')
    records = document.get('players')
    _require(isinstance(records, list) and len(records) == 738, 'expected 738 canonical players')
    slugs, pages = set(), set()
    for record in records:
        _require(isinstance(record, dict) and set(record) == {'slug', 'leaguepedia_page', 'relations'}, 'invalid fields')
        slug, page, relations = record['slug'], _identity(record['leaguepedia_page']), record['relations']
        _require(isinstance(slug, str) and re.fullmatch(r'[a-z0-9_-]{1,80}', slug)
                 and slug not in slugs and page and page not in pages, 'invalid/duplicate canonical identity')
        slugs.add(slug)
        pages.add(page)
        _require(isinstance(relations, dict) and set(relations) == RELATION_FIELDS, 'missing relation fields')
        for field, values in relations.items():
            _require(isinstance(values, list) and all(isinstance(value, str) and re.fullmatch(r'[a-z0-9_-]{1,80}', value) for value in values)
                     and values == sorted(set(values)), 'invalid relation list')
        _require(set(relations['won_teams']) <= set(relations['teams'])
                 and set(relations['won_players']) <= set(relations['players'])
                 and slug not in relations['players'], 'incoherent positive relations')
    by_slug = {row['slug']: row for row in records}
    for record in records:
        for opponent in record['relations']['players']:
            _require(opponent in slugs and record['slug'] in by_slug[opponent]['relations']['players'], 'asymmetric player relation')
    return records


def load_release():
    payload = gzip.decompress((Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / RELEASE_FILE).read_bytes())
    _require(sha256(payload).hexdigest() == RELEASE_SHA256, 'checksum mismatch')
    document = json.loads(payload)
    return document, validate_release(document)


def install_opponents(apps, schema_editor):
    document, records = load_release()
    Player = apps.get_model('players', 'Player')
    alias = schema_editor.connection.alias
    metadata = {key: document[key] for key in ('source', 'scope', 'complete_through_year', 'as_of', 'source_sha256')}
    with transaction.atomic(using=alias):
        existing = {player.slug: player for player in Player.objects.using(alias).select_for_update(no_key=True)
                    .filter(slug__in=[record['slug'] for record in records]).order_by('pk')}
        updates = []
        for record in records:
            player = existing.get(record['slug'])
            if player is None:
                continue
            attributes = player.attributes
            _require(isinstance(attributes, dict)
                     and _identity(attributes.get('leaguepedia_page')) == _identity(record['leaguepedia_page'])
                     and attributes.get('worlds_verified') is True,
                     f"canonical identity conflict for {record['slug']}")
            updated = {**attributes, 'worlds_opponents': {**metadata, 'complete': True, **record['relations']}}
            if updated != attributes:
                updates.append((player.pk, updated))
        # All identities are validated before any update. Concurrent submissions
        # keep their FK key-share locks; only non-key JSON attributes change.
        for pk, attributes in updates:
            Player.objects.using(alias).filter(pk=pk).update(attributes=attributes)


class Migration(migrations.Migration):
    dependencies = [('players', '0006_verified_career_roles')]
    operations = [migrations.RunPython(install_opponents, migrations.RunPython.noop)]
