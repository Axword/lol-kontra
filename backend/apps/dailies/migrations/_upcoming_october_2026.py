"""Reviewed future boards; preserve today's, archived and started games."""
from datetime import date
import hashlib
import json
from pathlib import Path

from django.utils import timezone

from ._guest_board_2026 import install_board

SOURCE = Path(__file__).resolve().parent.parent / 'fixtures/releases/upcoming_boards_2026_10_21_v1.json'
SHA256 = '43ba95e56eb8c63b82d0637f0c0e1e0fd38b6209f00cdf37b86c03233caf835b'


def load_boards():
    raw = SOURCE.read_text(encoding='utf-8').encode('utf-8')
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Upcoming board release SHA-256 mismatch')
    return json.loads(raw)['boards']


def install(apps, schema_editor, *, today=None):
    today = today or timezone.localdate()
    for board in load_boards():
        if date.fromisoformat(board['date']) > today:
            install_board(apps, schema_editor.connection.alias, board)
