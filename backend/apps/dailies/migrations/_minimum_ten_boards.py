"""Reviewed future boards under the ten-answer policy; never rewrite started games."""
from datetime import date
import hashlib
import json
from pathlib import Path

from django.utils import timezone
from ._guest_board_2026 import install_board

SOURCE = Path(__file__).resolve().parent.parent / 'fixtures/releases/upcoming_boards_minimum_ten_v2.json'
SHA256 = '5215bcd22abce4c3c97f8c1350aff9a652f83690ade0cd4458493fb8b21096e9'


def load_boards():
    raw = SOURCE.read_text(encoding='utf-8').encode('utf-8')
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Minimum-ten release SHA-256 mismatch')
    return json.loads(raw)['boards']


def install(apps, schema_editor, *, today=None):
    today = today or timezone.localdate()
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Submission = apps.get_model('submissions', 'Submission')
    for spec in load_boards():
        if date.fromisoformat(spec['date']) <= today:
            continue
        existing = Daily.objects.using(alias).select_for_update().filter(date=spec['date']).first()
        if existing and (existing.author_name.strip() or Submission.objects.using(alias).filter(daily_id=existing.pk).exists()):
            continue
        install_board(apps, alias, spec)
        Daily.objects.using(alias).filter(date=spec['date']).update(minimum_candidates=10)
