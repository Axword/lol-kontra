from copy import deepcopy
import gzip
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import TestCase

from .management.commands.refresh_worlds_history import Command
from .models import Player
from .test_worlds_achievements import MAIN, add_series, snapshot


class RefreshWorldsHistoryTests(TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.enterContext(self.settings(BASE_DIR=self.root / 'backend'))
        self.fixture = self.root / 'players.json'
        self.snapshot = self.root / 'snapshot.json.gz'
        self.source = self.root / 'results.json.gz'
        self.report = self.root / 'report.json'
        self.attributes = {'leaguepedia_page': 'FabFabulous', 'worlds_verified': True,
                           'portrait_url': 'https://example.org/portrait.png', 'custom': {'keep': 42},
                           'worlds_titles': [2000], 'worlds_finals': [2000]}
        self.player = Player.objects.create(slug='stable-id', nickname='Different Nick',
                                            attributes=deepcopy(self.attributes),
                                            career_stats={'worlds': {'games': 123}}, worlds_titles_count=9)
        self.records = [{'slug': 'stable-id', 'nickname': 'Different Nick', 'worlds_titles_count': 9,
                         'career_stats': {'worlds': {'games': 456}},
                         'attributes': {**deepcopy(self.attributes), 'fixture_custom': 'keep too'}}]
        self.fixture.write_text(json.dumps(self.records), encoding='utf8')
        data = snapshot()
        data['players'] = [{'page': 'FabFabulous'}]
        add_series(data, MAIN, 'Finals', 1, ('A', 'B'), [1, 1],
                   rosters={'B': ['fabFabulous', 'B-1', 'B-2', 'B-3', 'B-4']})
        self.data = data
        self._write_snapshot()

    def _write_snapshot(self):
        self.snapshot.write_bytes(gzip.compress(json.dumps(self.data).encode(), mtime=0))
        self.source.write_bytes(gzip.compress(json.dumps({
            'source': 'Leaguepedia', 'complete': True, 'as_of': self.data['as_of'], 'results': [],
        }).encode(), mtime=0))

    def run_command(self, **extra):
        call_command('refresh_worlds_history', fixture=str(self.fixture), snapshot=str(self.snapshot),
                     eliminations_source=str(self.source), report=str(self.report), stdout=io.StringIO(), **extra)

    def test_apply_preserves_identity_portraits_career_stats_and_other_metadata(self):
        self.run_command(apply=True)
        self.player.refresh_from_db()
        updated = json.loads(self.fixture.read_text(encoding='utf8'))[0]
        self.assertEqual(Player.objects.count(), 1)
        self.assertEqual(Player.objects.get(slug='stable-id').pk, self.player.pk)
        self.assertEqual(self.player.nickname, 'Different Nick')
        self.assertEqual(self.player.career_stats, {'worlds': {'games': 123}})
        self.assertEqual(updated['career_stats'], {'worlds': {'games': 456}})
        self.assertEqual(updated['attributes']['fixture_custom'], 'keep too')
        self.assertNotIn('fixture_custom', self.player.attributes)
        for attrs in (self.player.attributes, updated['attributes']):
            self.assertEqual(attrs['portrait_url'], self.attributes['portrait_url'])
            self.assertEqual(attrs['custom'], {'keep': 42})
            self.assertEqual(attrs['worlds_titles'], [])
            self.assertEqual(attrs['worlds_finals'], [2018])
            self.assertEqual(attrs['worlds_eliminations']['final'], [2018])
        self.assertEqual(self.player.worlds_titles_count, 0)
        report = json.loads(self.report.read_text())
        self.assertEqual((report['fixture_updated'], report['database_updated']), (1, 1))
        self.assertEqual(Path(report['backup']).read_text(), json.dumps(self.records))

    def test_default_and_explicit_dry_run_leave_fixture_and_database_unchanged(self):
        original = self.fixture.read_bytes()
        for options in ({}, {'dry_run': True}):
            self.run_command(**options)
            self.player.refresh_from_db()
            self.assertEqual(self.player.attributes, self.attributes)
            self.assertEqual(self.player.worlds_titles_count, 9)
            self.assertEqual(self.fixture.read_bytes(), original)
            self.assertFalse(json.loads(self.report.read_text())['applied'])

    def test_unknown_history_deletes_stale_positive_instead_of_claiming_verified_empty(self):
        event = '2026 Season World Championship/Main Event'
        self.data['tournaments'] = [{'OverviewPage': event}]
        self.data['rows'], self.data['achievements_source']['schedule'] = [], []
        add_series(self.data, event, 'Round 1', 1, ('A', 'B'), [1], best_of=1, date='2026-10-17',
                   rosters={'B': ['fabFabulous', 'B-1', 'B-2', 'B-3', 'B-4']})
        self._write_snapshot()
        self.run_command(apply=True)
        self.player.refresh_from_db()
        self.assertNotIn('worlds_titles', self.player.attributes)
        self.assertNotIn('worlds_finals', self.player.attributes)
        self.assertNotIn('worlds_eliminations', self.player.attributes)
        self.assertFalse(self.player.attributes['worlds_titles_verified'])

    def test_report_failure_rolls_back_database_and_atomically_restores_fixture(self):
        original = self.fixture.read_bytes()
        write_json = Command._write_json

        def fail_report(path, value):
            if path == self.report:
                raise OSError('Report storage failed')
            return write_json(path, value)

        with patch.object(Command, '_write_json', side_effect=fail_report):
            with self.assertRaisesRegex(CommandError, 'Report storage failed'):
                self.run_command(apply=True)
        self.player.refresh_from_db()
        self.assertEqual(self.player.attributes, self.attributes)
        self.assertEqual(self.player.worlds_titles_count, 9)
        self.assertEqual(self.fixture.read_bytes(), original)

    def test_repeating_apply_is_idempotent(self):
        self.run_command(apply=True)
        original = self.fixture.read_bytes()
        self.run_command(apply=True)
        report = json.loads(self.report.read_text())
        self.assertEqual((report['fixture_updated'], report['database_updated']), (0, 0))
        self.assertIsNone(report['backup'])
        self.assertEqual(self.fixture.read_bytes(), original)

    def test_stale_source_is_rejected_before_mutation(self):
        self.source.write_bytes(gzip.compress(json.dumps({
            'source': 'Leaguepedia', 'complete': True, 'as_of': '2025-01-01', 'results': [],
        }).encode(), mtime=0))
        original = self.fixture.read_bytes()
        with self.assertRaisesRegex(CommandError, 'as_of'):
            self.run_command(apply=True)
        self.player.refresh_from_db()
        self.assertEqual(self.player.attributes, self.attributes)
        self.assertEqual(self.fixture.read_bytes(), original)
