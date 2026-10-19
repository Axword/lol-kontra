"""Add narrowly verified career roles without changing Worlds-only evidence."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


SOURCE_FILE = 'career_roles_2026_10_19_v1.json'
SOURCE_SHA256 = '76d3bf698c138700f361f910550ebbef92f7f8aba9dd627bd9840dbcf80090db'
ROLE_ORDER = ('top', 'jungle', 'mid', 'adc', 'support')


@lru_cache(maxsize=1)
def _corrections():
    # Text normalization keeps the pinned digest stable across Git CRLF checkouts.
    payload = (Path(__file__).resolve().parent / 'fixtures' / 'releases' / SOURCE_FILE).read_text(encoding='utf-8').encode('utf-8')
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError('Career role evidence checksum mismatch')
    document = json.loads(payload)
    return {row['slug']: row for row in document['corrections']}


def with_verified_career_roles(record):
    """Return an overlaid record only for the exact canonical source identity.

    Nationality, a matching nickname, champions and Worlds-only role history
    are never used to infer an additional career role.
    """
    correction = _corrections().get(record.get('slug'))
    attrs = record.get('attributes') or {}
    if not correction or attrs.get('leaguepedia_page') != correction['leaguepedia_page']:
        return record
    roles = set(record.get('secondary_roles') or []) | set(correction['roles'])
    roles.discard(record.get('primary_role'))
    return {**record, 'secondary_roles': sorted(roles, key=ROLE_ORDER.index)}
