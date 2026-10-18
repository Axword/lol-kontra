from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from .leaguepedia_source import SourceError
from .models import Player
from .portraits import _export_all, apply_portraits, fetch_player_portraits, parse_imageinfo


URL = 'https://static.wikia.nocookie.net/lolesports_gamepedia_en/images/a/ab/Portrait.png/revision/latest/scale-to-width-down/128'


def source(status='available'):
    return {'source': 'Leaguepedia', 'fetched_at': '2026-10-18T10:00:00+00:00', 'players': {
        'Canonical Player': {'status': status, 'url': URL, 'file': 'File:Portrait.png', 'revid': 123},
    }}


class PortraitMetadataTests(unittest.TestCase):
    def test_mediawiki_normalization_and_redirects_preserve_real_url_and_revision(self):
        payload = {'query': {
            'normalized': [{'from': 'File:Player_old.png', 'to': 'File:Player old.png'}],
            'redirects': [{'from': 'File:Player old.png', 'to': 'File:Portrait.png'}],
            'pages': [{'title': 'File:Portrait.png', 'pageid': 12, 'lastrevid': 123, 'imageinfo': [{
                'thumburl': URL, 'mime': 'image/png', 'sha1': 'abc', 'timestamp': '2026-01-01T00:00:00Z',
            }]}],
        }}
        portrait = parse_imageinfo(payload, ['File:Player_old.png'])['File:Player_old.png']
        self.assertEqual(portrait['status'], 'available')
        self.assertEqual(portrait['url'], URL)
        self.assertEqual(portrait['file'], 'File:Portrait.png')
        self.assertEqual(portrait['revid'], 123)
        self.assertEqual(portrait['sha1'], 'abc')

    def test_omitted_image_is_unknown_but_explicit_missing_is_missing(self):
        data = parse_imageinfo({'query': {'pages': [{'title': 'File:Missing.png', 'missing': True}]}},
                               ['File:Missing.png', 'File:Omitted.png'])
        self.assertEqual(data['File:Missing.png']['status'], 'missing')
        self.assertEqual(data['File:Omitted.png']['status'], 'unknown')

    def test_errors_and_invalid_image_urls_are_not_claimed_missing(self):
        with self.assertRaises(SourceError):
            parse_imageinfo({'error': {'code': 'ratelimited'}}, ['File:Portrait.png'])
        for url, mime in [('javascript:alert(1)', 'image/png'), (URL, 'text/html'), ('https://[invalid', 'image/png')]:
            data = parse_imageinfo({'query': {'pages': [{'title': 'File:Portrait.png', 'imageinfo': [
                {'thumburl': url, 'mime': mime},
            ]}]}}, ['File:Portrait.png'])
            self.assertEqual(data['File:Portrait.png']['status'], 'unknown')

    def test_enrichment_changes_only_portrait_metadata_and_uses_source_identity(self):
        records = [{'slug': 'old-player-id', 'nickname': 'Other Nick', 'career_stats': {'worlds': {'games': 100}},
                    'attributes': {'leaguepedia_page': 'Canonical Player', 'worlds_titles': [2018], 'custom': 1}}]
        before = deepcopy(records)
        updated, report = apply_portraits(records, source())
        self.assertEqual(records, before)
        self.assertEqual(updated[0]['career_stats'], before[0]['career_stats'])
        self.assertEqual(updated[0]['slug'], 'old-player-id')
        self.assertEqual(updated[0]['attributes']['worlds_titles'], [2018])
        self.assertEqual(updated[0]['attributes']['custom'], 1)
        self.assertEqual(updated[0]['attributes']['portrait_url'], URL)
        self.assertEqual(updated[0]['attributes']['portrait_revid'], 123)
        self.assertEqual(report['available'], 1)

    def test_failed_refresh_keeps_previous_photo_and_is_not_missing(self):
        records = [{'attributes': {'leaguepedia_page': 'Canonical Player', 'portrait_url': URL,
                                  'portrait_source': 'Leaguepedia'}}]
        updated, report = apply_portraits(records, source('unknown'))
        self.assertEqual(updated, records)
        self.assertEqual((report['unknown'], report['missing'], report['updated']), (1, 0, 0))

    def test_confirmed_missing_removes_stale_leaguepedia_photo(self):
        records = [{'attributes': {'leaguepedia_page': 'Canonical Player', 'portrait_url': URL,
                                  'portrait_source': 'Leaguepedia'}}]
        updated, report = apply_portraits(records, source('missing'))
        self.assertNotIn('portrait_url', updated[0]['attributes'])
        self.assertEqual(updated[0]['attributes']['portrait_status'], 'missing')
        self.assertEqual(report['missing'], 1)

    def test_failed_cargo_fetch_reports_unknown_without_false_missing(self):
        with patch('apps.players.portraits.CargoExport') as client:
            client.return_value.query.side_effect = SourceError('Network failed')
            result = fetch_player_portraits(['Canonical Player'], 'unused', progress=lambda *a, **k: None)
        self.assertEqual(result['players']['Canonical Player']['status'], 'unknown')
        self.assertTrue(result['errors'])

    def test_automatic_infobox_photo_uses_latest_source_order(self):
        with patch('apps.players.portraits.CargoExport'), \
             patch('apps.players.portraits._export_all', side_effect=[
                 [{'page': 'Canonical Player', 'image': None}],
                 [{'page': 'Canonical Player', 'image': 'Current.png', 'sort_date': '2026-01-01'},
                  {'page': 'Canonical Player', 'image': 'Old.png', 'sort_date': '2020-01-01'}],
             ]), patch('apps.players.portraits._api_imageinfo', return_value={
                 'File:Current.png': {'status': 'available', 'file': 'File:Current.png', 'url': URL},
             }) as imageinfo:
            result = fetch_player_portraits(['Canonical Player'], 'unused', progress=lambda *a, **k: None)
        self.assertEqual(result['players']['Canonical Player']['file'], 'File:Current.png')
        self.assertEqual(imageinfo.call_args.args[1], ['File:Current.png'])

    def test_truncated_export_does_not_become_missing_metadata(self):
        with patch('apps.players.portraits.CargoExport') as factory:
            client = factory.return_value
            client.query.side_effect = [[{'n': 3}], [{'page': 'A'}, {'page': 'B'}], []]
            with self.assertRaises(SourceError):
                _export_all(client, tables='Players', fields='OverviewPage=page', where='1=1')


class PortraitCommandTests(TestCase):
    def test_offline_apply_preserves_player_ids_stats_and_unrelated_attributes(self):
        player = Player.objects.create(slug='stable-id', nickname='Player',
                                       attributes={'leaguepedia_page': 'Canonical Player', 'worlds_titles': [2018]},
                                       career_stats={'worlds': {'games': 123}})
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            fixture, metadata, report = [directory / name for name in ('players.json', 'source.json', 'report.json')]
            record = {'slug': 'stable-id', 'nickname': 'Player', 'career_stats': player.career_stats,
                      'attributes': player.attributes}
            fixture.write_text(json.dumps([record]), encoding='utf-8')
            metadata.write_text(json.dumps(source()), encoding='utf-8')
            with patch('apps.players.management.commands.refresh_player_portraits.fetch_player_portraits') as fetch:
                call_command('refresh_player_portraits', fixture=str(fixture), source=str(metadata),
                             report=str(report), apply=True, stdout=io.StringIO())
                fetch.assert_not_called()
            player.refresh_from_db()
            updated = json.loads(fixture.read_text(encoding='utf-8'))[0]
            self.assertEqual(Player.objects.count(), 1)
            self.assertEqual(Player.objects.get(slug='stable-id').pk, player.pk)
            self.assertEqual(player.career_stats, {'worlds': {'games': 123}})
            self.assertEqual(player.attributes['worlds_titles'], [2018])
            self.assertEqual(updated['career_stats'], record['career_stats'])
            self.assertEqual(player.attributes['portrait_url'], URL)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['database_updated'], 1)
