"""Publish historical playoff clues while preserving all earlier game revisions."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from django.db import migrations, transaction
from django.utils import timezone

RELEASE_FILE = 'worlds_playoffs_2026_11_03_v2.json'
RELEASE_SHA256 = 'f17cee67390fed795af3db0cc71d0d9793b6f9a44bd8eba759bc1b107f552de7'
ROLES = ['top', 'jungle', 'mid', 'adc', 'support']


def load_release():
    raw = (Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / RELEASE_FILE).read_text(encoding='utf-8').encode('utf-8')
    if sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError('Historical playoff board release checksum mismatch')
    data = json.loads(raw)
    if (data['schema_version'] != 1 or data['release'] != 'worlds-playoffs-2026-11-03-v2'
            or [b['date'] for b in data['boards']] != ['2026-11-03', '2026-11-04']):
        raise ValueError('Unexpected historical playoff board release')
    for board in data['boards']:
        if ([s['role'] for s in board['slots']] != ROLES
                or any(not 1 <= len(s['conditions']) <= 2 or len(set(s['audited_candidates'])) < 2
                       for s in board['slots'])):
            raise ValueError('Incomplete audited historical playoff board')
    return data


def install(apps, schema_editor):
    source = load_release()
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Player = apps.get_model('players', 'Player')
    # Schema-only migration tests have no source identities. Production
    # bootstrap independently requires the complete verified player release.
    if not Player.objects.using(alias).exists():
        return
    required = {slug for b in source['boards'] for s in b['slots'] for slug in s['audited_candidates']}
    if set(Player.objects.using(alias).filter(slug__in=required).values_list('slug', flat=True)) != required:
        raise ValueError('Historical playoff board candidate identities are missing')
    with transaction.atomic(using=alias):
        for definition in source['boards']:
            day = date.fromisoformat(definition['date'])
            previous = Daily.objects.using(alias).select_for_update().filter(date=day, is_current=True).first()
            if previous and previous.locale_seed == definition['locale_seed']:
                continue
            if previous:
                Daily.objects.using(alias).filter(pk=previous.pk).update(is_current=False)
            board = Daily.objects.using(alias).create(
                date=day, is_current=True, status='published', reveal_mode='instant',
                published_at=timezone.now(), minimum_candidates=None,
                **{key: definition[key] for key in (
                    'locale_seed', 'author_name', 'author_url', 'author_description',
                )},
            )
            for position, slot in enumerate(definition['slots'], 1):
                row = Slot.objects.using(alias).create(
                    daily_id=board.pk, position=position, role=slot['role'],
                    label_pl=slot['role'].capitalize(), label_en=slot['role'].capitalize(),
                )
                Condition.objects.using(alias).bulk_create([
                    Condition(slot_id=row.pk, order=order, **condition)
                    for order, condition in enumerate(slot['conditions'])
                ])


class Migration(migrations.Migration):
    dependencies = [('dailies', '0025_historical_worlds_conditions')]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
