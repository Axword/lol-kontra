"""Pure, identity-preserving merge of independently validated source exports."""
from copy import deepcopy

from .career_source import build_career_overlay
from .worlds_achievements import enrich_worlds_achievements
from .worlds_eliminations import enrich_worlds_eliminations
from .worlds_import import _key, build_worlds_players


WORLD_ATTRIBUTES = frozenset((
    'worlds_verified', 'worlds_appearances', 'worlds_teams', 'worlds_team_years', 'worlds_roles',
    'worlds_playin_appearances', 'worlds_playin', 'worlds_titles', 'worlds_titles_verified',
    'worlds_finals', 'worlds_semifinals', 'worlds_group_escapes', 'worlds_achievements',
    'worlds_eliminations', 'worlds_eliminations_meta', 'pentakills_worlds', 'pentakills_worlds_verified',
))


def refresh_worlds_records(snapshot, records, career_snapshot=None):
    """Replace validated aggregates, never increment them or mutate game records.

    Source-page metadata, portraits, leagues, slugs and unrelated career data
    remain unchanged. A partial career export refreshes only its named players.
    Running the same input again is idempotent, including champion game counts.
    """
    rebuilt, report = build_worlds_players(snapshot, records)
    rebuilt, report['achievements'] = enrich_worlds_achievements(snapshot, rebuilt)
    rebuilt, report['eliminations'] = enrich_worlds_eliminations(snapshot, rebuilt)
    fresh_by_slug = {record['slug']: record for record in rebuilt}
    if set(fresh_by_slug) != {record['slug'] for record in records} or report['new_players']:
        raise ValueError('A stats refresh cannot create or replace player identities')
    career_by_slug = {}
    if career_snapshot is not None:
        if career_snapshot.get('as_of') != snapshot['as_of']:
            raise ValueError('Career and Worlds refresh sources must share as_of')
        pages = {_key(row.get('page')) for row in career_snapshot.get('totals', [])}
        targets = [record for record in records if _key(record.get('attributes', {}).get('leaguepedia_page')) in pages]
        overlay = build_career_overlay(career_snapshot, targets)
        career_by_slug = {record['slug']: record['career_stats']['career'] for record in overlay['players']}
        report['career'] = overlay['report']
    updated = deepcopy(records)
    for record in updated:
        if record.get('attributes', {}).get('worlds_verified') is not True:
            continue
        fresh = fresh_by_slug[record['slug']]
        for key in WORLD_ATTRIBUTES:
            if key in fresh['attributes']:
                record['attributes'][key] = deepcopy(fresh['attributes'][key])
            else:
                record['attributes'].pop(key, None)
        record['worlds_count'] = fresh['worlds_count']
        record['worlds_titles_count'] = fresh['worlds_titles_count']
        record.setdefault('career_stats', {})['worlds'] = deepcopy(fresh['career_stats']['worlds'])
        if record['slug'] in career_by_slug:
            record['career_stats']['career'] = deepcopy(career_by_slug[record['slug']])
    report['career_refreshed_slugs'] = sorted(career_by_slug)
    report['changed_records'] = sum(before != after for before, after in zip(records, updated))
    return updated, report
