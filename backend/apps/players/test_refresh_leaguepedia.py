import gzip
import json
import os
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.core.management.base import CommandError
from django.db import DatabaseError
from django.test import SimpleTestCase

from .management.commands import refresh_leaguepedia as refresh


class RefreshFileRollbackTests(SimpleTestCase):
    def run_refresh(self, folder, atomic, replace=None, compressed=False, save_snapshot=False):
        source = folder / ('input.json.gz' if compressed else 'input.json')
        payload = json.dumps({'as_of': '2026-10-18T09:46:04+00:00', 'rows': []}).encode()
        source.write_bytes(gzip.compress(payload) if compressed else payload)
        existing = folder / 'existing.json'
        existing.write_text('[]', encoding='utf-8')
        command = refresh.Command(stdout=StringIO())
        report = {'confirmed_players': 10, 'games': 1, 'new_players': 0}
        options = {
            'snapshot': str(source), 'cache_dir': str(folder / 'cache'),
            'output': str(folder / 'output.json'), 'report': str(folder / 'report.json'),
            'save_snapshot': str(folder / 'saved.json') if save_snapshot else None,
            'apply': True, 'dry_run': False,
        }
        with patch.object(refresh, 'FIXTURE', existing), \
                patch.object(refresh, 'prepare_snapshot', side_effect=lambda value, *_args, **_kwargs: value), \
                patch.object(refresh, 'build_worlds_players', return_value=([{'slug': 'new'}], report)), \
                patch.object(refresh, 'enrich_worlds_achievements', side_effect=lambda _snapshot, records: (records, {})), \
                patch.object(refresh, 'call_command') as seed, \
                patch.object(refresh.transaction, 'atomic', return_value=atomic), \
                patch.object(refresh.os, 'replace', side_effect=replace or os.replace):
            with self.assertRaises(CommandError):
                command.handle(**options)
            self.assertEqual(seed.call_count, 1)
            self.assertEqual(seed.call_args.args[0], 'seed_players')
            self.assertNotIn('clear', seed.call_args.kwargs)

    def test_report_replace_failure_restores_fixture_and_rolls_back_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            output, report = folder / 'output.json', folder / 'report.json'
            output.write_bytes(b'original fixture\n')
            report.write_bytes(b'original report\n')
            real_replace = os.replace
            calls = 0

            def fail_second_replace(source, target):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise PermissionError('report cannot be replaced')
                return real_replace(source, target)

            atomic = MagicMock()
            atomic.__exit__.return_value = False
            self.run_refresh(folder, atomic, replace=fail_second_replace)
            self.assertEqual(output.read_bytes(), b'original fixture\n')
            self.assertEqual(report.read_bytes(), b'original report\n')
            self.assertIs(atomic.__exit__.call_args.args[0], PermissionError)
            self.assertFalse(list(folder.glob('.worlds-backup-*')))
            self.assertEqual({path.name for path in folder.iterdir()},
                             {'input.json', 'existing.json', 'output.json', 'report.json'})

    def test_database_commit_failure_restores_all_files_and_keeps_gzip_input_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            originals = {'output.json': b'old fixture', 'report.json': b'old report', 'saved.json': b'old snapshot'}
            for name, data in originals.items():
                (folder / name).write_bytes(data)
            atomic = MagicMock()
            atomic.__exit__.side_effect = DatabaseError('commit failed')
            self.run_refresh(folder, atomic, compressed=True, save_snapshot=True)
            for name, data in originals.items():
                self.assertEqual((folder / name).read_bytes(), data)
            self.assertFalse(list(folder.glob('.worlds-backup-*')))
            self.assertEqual({path.name for path in folder.iterdir()},
                             {'input.json.gz', 'existing.json', *originals})

    def test_commit_failure_removes_files_that_did_not_exist_before_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            atomic = MagicMock()
            atomic.__exit__.side_effect = DatabaseError('commit failed')
            self.run_refresh(folder, atomic)
            self.assertFalse((folder / 'output.json').exists())
            self.assertFalse((folder / 'report.json').exists())
            self.assertEqual({path.name for path in folder.iterdir()}, {'input.json', 'existing.json'})
