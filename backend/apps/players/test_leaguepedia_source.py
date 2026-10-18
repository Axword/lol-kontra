import tempfile
from pathlib import Path
from unittest.mock import Mock
from datetime import datetime, timezone

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from .leaguepedia_source import CargoExport, SourceError, add_scoreboard_supplements, prepare_snapshot, sql_string, validate_worlds_catalogue, worlds_year
from .models import Player


def test_worlds_scope_excludes_regional_qualifiers_and_other_world_championships():
    for page, year in [('Season 1 World Championship', 2011), ('Season 2 World Championship', 2012),
                       ('Season 3 World Championship', 2013), ('2014 Season World Championship', 2014),
                       ('2025 Season World Championship/Play-In', 2025), ('2026 Season World Championship/Main Event', 2026)]:
        assert worlds_year(page) == year
    for page in ['2023 Worlds Qualifying Series', 'IEM Season X - World Championship',
                 'Season 1 World Championship/Qualifiers/Europe', '2025 Season World Championship',
                 '2025 Season World Championship/Play-In/Qualifiers', 'Season 4 World Championship']:
        assert worlds_year(page) is None


def test_export_rejects_mediawiki_errors_returned_with_http_200():
    with tempfile.TemporaryDirectory() as folder:
        client = CargoExport(folder, interval=0)
        response = Mock(status_code=200)
        response.json.return_value = {'error': {'code': 'ratelimited'}}
        client.session.get = Mock(return_value=response)
        with pytest.raises(SourceError, match='ratelimited'):
            client.query(tables='ScoreboardPlayers', fields='Link')
        assert not list(Path(folder).glob('*.json'))


def test_export_respects_http_rate_limit_without_retrying():
    with tempfile.TemporaryDirectory() as folder:
        client = CargoExport(folder, interval=0)
        client.session.get = Mock(return_value=Mock(status_code=429, headers={'Retry-After': '120'}))
        with pytest.raises(SourceError, match='120'):
            client.query(tables='Players', fields='ID')
        assert client.session.get.call_count == 1


def test_checked_pagination_rejects_truncated_and_changing_results():
    with tempfile.TemporaryDirectory() as folder:
        client = CargoExport(folder, interval=0, progress=Mock())
        client.query = Mock(side_effect=[[{'n': 3}], [{'id': 1}, {'id': 2}], []])
        with pytest.raises(SourceError, match='Truncated'):
            client.all('Players', 'ID', 'active', 'ID ASC', limit=2)
        client.query = Mock(side_effect=[[{'n': 2}], [{'id': 1}, {'id': 2}], [{'n': 3}]])
        with pytest.raises(SourceError, match='changed'):
            client.all('Players', 'ID', 'active', 'ID ASC', limit=2)


def test_checked_pagination_preserves_order_and_offset():
    with tempfile.TemporaryDirectory() as folder:
        client = CargoExport(folder, interval=0, progress=Mock())
        client.query = Mock(side_effect=[[{'n': 3}], [{'id': 1}, {'id': 2}], [{'id': 3}], [{'n': 3}]])
        assert client.all('Players', 'ID', 'active', 'ID ASC', limit=2) == [{'id': 1}, {'id': 2}, {'id': 3}]
        assert client.query.call_args_list[2].kwargs['offset'] == 2
        assert client.query.call_args_list[2].kwargs['order_by'] == 'ID ASC'
        assert client.query.call_args_list[-1].kwargs['refresh'] is True


def test_sql_literals_escape_player_names_without_changing_identity():
    assert sql_string("O'Brien") == "'O''Brien'"


def test_revision_pinned_supplement_is_idempotent_and_rejects_partial_overlap():
    snapshot = {'as_of': '2026-10-18T09:46:04+00:00', 'rows': [], 'aliases': []}
    recovered = add_scoreboard_supplements(snapshot)
    assert len(recovered['rows']) == 150
    assert len(snapshot['rows']) == 0
    assert len(add_scoreboard_supplements(recovered)['rows']) == 150
    with pytest.raises(SourceError, match='conflicts'):
        add_scoreboard_supplements({**snapshot, 'rows': recovered['rows'][:1]})
    recovered['rows'][0]['champion'] = 'INVALID'
    with pytest.raises(SourceError, match='conflicts'):
        add_scoreboard_supplements(recovered)


def test_supplement_cannot_add_games_after_the_snapshot_cutoff():
    snapshot = {'as_of': '2023-01-01T00:00:00+00:00', 'rows': [], 'aliases': []}
    assert add_scoreboard_supplements(snapshot)['rows'] == []


def test_offline_refresh_requires_independent_schedule_without_network():
    with pytest.raises(SourceError, match='independent MatchSchedule'):
        import gzip, json
        snapshot = json.loads(gzip.decompress((Path(__file__).parent / 'fixtures' / 'worlds_source_snapshot.json.gz').read_bytes()))
        snapshot.pop('achievements_source')
        prepare_snapshot(snapshot, '.', offline=True)


def test_offline_catalogue_cannot_silently_drop_a_season_or_play_in():
    import gzip, json
    snapshot = json.loads(gzip.decompress((Path(__file__).parent / 'fixtures' / 'worlds_source_snapshot.json.gz').read_bytes()))
    cutoff = datetime(2026, 10, 18, tzinfo=timezone.utc)
    validate_worlds_catalogue(snapshot['tournaments'], cutoff)
    for missing in ['2014 Season World Championship', '2023 Season World Championship/Play-In']:
        reduced = [row for row in snapshot['tournaments'] if row['OverviewPage'] != missing]
        with pytest.raises(SourceError, match='Incomplete Worlds tournament catalogue'):
            validate_worlds_catalogue(reduced, cutoff)


class WorldsEligibilityApiTests(TestCase):
    def test_confirmed_non_worlds_players_are_not_searchable(self):
        Player.objects.create(slug='iem-only', nickname='Excluded', attributes={'worlds_verified': False})
        Player.objects.create(slug='worlds', nickname='Included', attributes={'worlds_verified': True})
        Player.objects.create(slug='legacy', nickname='Legacy')
        client = APIClient()
        for path in ['/api/v1/players/', '/api/v1/players/autocomplete/?q=']:
            response = client.get(path)
            assert response.status_code == 200
            rows = response.data if isinstance(response.data, list) else response.data['results']
            slugs = {row['slug'] for row in rows}
            assert slugs == {'worlds', 'legacy'}
