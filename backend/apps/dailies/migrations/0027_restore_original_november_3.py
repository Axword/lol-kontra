"""Restore the original November 3 board and its existing games, without deletions."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from django.db import migrations, transaction
from django.utils import timezone

RELEASE_FILE = 'original_daily_2026_11_03_v1.json'
RELEASE_SHA256 = '90bf83e52be7fec27a8cc6e152c8a9c52ae03e7dbb23753f7df02bd923b54f30'
DAY = date(2026, 11, 3)


def load_release():
    raw = (Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / RELEASE_FILE).read_text(encoding='utf-8').encode('utf-8')
    if sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError('Original board checksum mismatch')
    data = json.loads(raw)
    if (data['schema_version'] != 1 or data['date'] != DAY.isoformat()
            or data['release'] != 'original-daily-2026-11-03-v1'
            or [s['role'] for s in data['slots']] != ['top', 'jungle', 'mid', 'adc', 'support']):
        raise ValueError('Unexpected original board release')
    return data


def definition(board):
    return [{
        **{key: getattr(slot, key) for key in ('position', 'role', 'label_pl', 'label_en')},
        'conditions': [{key: getattr(c, key) for key in (
            'condition_type', 'operator', 'value', 'label_pl', 'label_en', 'order',
        )} for c in slot.conditions.order_by('order', 'pk')],
    } for slot in board.slots.order_by('position')]


def restore(apps, schema_editor):
    source = load_release()
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Player = apps.get_model('players', 'Player')
    if not Player.objects.using(alias).exists():
        return
    with transaction.atomic(using=alias):
        boards = list(Daily.objects.using(alias).select_for_update().filter(date=DAY).order_by('pk'))
        matches = [board for board in boards if definition(board) == source['slots']]
        original = next((board for board in matches if board.pk == source['source_daily_id']),
                        matches[0] if matches else None)
        if original and original.is_current:
            return
        Daily.objects.using(alias).filter(date=DAY, is_current=True).update(is_current=False)
        if original:
            # Keep the original IDs, answers, stats, comments and timestamps.
            Daily.objects.using(alias).filter(pk=original.pk).update(is_current=True)
            return
        # Fresh installations do not contain production's original board.
        # Reconstruct its frozen requirements, without importing any user data.
        original = Daily.objects.using(alias).create(
            date=DAY, is_current=True, status='published', reveal_mode='instant',
            locale_seed=source['release'], published_at=timezone.now(), minimum_candidates=None,
        )
        for slot in source['slots']:
            row = Slot.objects.using(alias).create(daily_id=original.pk,
                **{key: slot[key] for key in ('position', 'role', 'label_pl', 'label_en')})
            Condition.objects.using(alias).bulk_create([
                Condition(slot_id=row.pk, **condition) for condition in slot['conditions']
            ])


class Migration(migrations.Migration):
    dependencies = [('dailies', '0026_historical_playoff_boards')]
    operations = [migrations.RunPython(restore, migrations.RunPython.noop)]
