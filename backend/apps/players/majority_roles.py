"""Tournament-majority roles used for new guesses, including archived boards."""
from functools import lru_cache
import gzip
from hashlib import sha256
import json
from pathlib import Path

SOURCE_FILE = 'majority_roles_2026_10_20_v1.json.gz'
SOURCE_SHA256 = '6c0e968164c61e564f92d66fd8ac541fc458957567ba95a335df783a71cac0a9'
POLICY = 'majority_worlds_or_major_league_roles'


@lru_cache(maxsize=1)
def role_evidence():
    payload = (Path(__file__).parent / 'fixtures' / 'releases' / SOURCE_FILE).read_bytes()
    if sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError('Majority-role evidence checksum mismatch')
    data = json.loads(gzip.decompress(payload))
    if data.get('scope') != POLICY or data.get('minimum_tournaments') != 1:
        raise ValueError('Unexpected role qualification policy')
    for player in data['players']:
        for evidence in player['evidence']:
            if (evidence['scope'] not in ('worlds', 'major_league')
                    or evidence['role'] not in ('top', 'jungle', 'mid', 'adc', 'support')
                    or not 0 < evidence['games'] <= evidence['team_games']
                    or evidence['games'] * 2 <= evidence['team_games']):
                raise ValueError('Role does not have a strict tournament majority')
    return {player['slug']: player for player in data['players']}


def qualified_roles(player, worlds_only=False):
    entry = role_evidence().get(getattr(player, 'slug', ''))
    if not entry or entry['leaguepedia_page'] != player.attributes.get('leaguepedia_page'):
        return set()
    return {row['role'] for row in entry['evidence'] if not worlds_only or row['scope'] == 'worlds'}
