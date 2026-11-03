"""Replace two boards without rewriting any existing game or saved roster."""
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

from django.db import migrations, transaction
from django.utils import timezone

RELEASE_FILE = 'worlds_playoffs_2026_11_03_v1.json'
RELEASE_SHA256 = '226062d42335eecd31b0e135b3a71588af8040f6013ae9b1cb95ee3c8006f69c'
ROLES = ['top', 'jungle', 'mid', 'adc', 'support']


def load_release():
    raw = (Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / RELEASE_FILE).read_text(encoding='utf-8').encode('utf-8')
    if sha256(raw).hexdigest() != RELEASE_SHA256:
        raise ValueError('Playoff board release checksum mismatch')
    data = json.loads(raw)
    if (data['schema_version'] != 1 or data['release'] != 'worlds-playoffs-2026-11-03-v1'
            or [b['date'] for b in data['boards']] != ['2026-11-03', '2026-11-04']):
        raise ValueError('Unexpected playoff board release')
    for board in data['boards']:
        if ([s['role'] for s in board['slots']] != ROLES
                or any(not 1 <= len(s['conditions']) <= 2 or len(set(s['audited_candidates'])) < 3
                       for s in board['slots'])):
            raise ValueError('Incomplete audited playoff board')
    return data


def install(apps, schema_editor):
    source = load_release()
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Player = apps.get_model('players', 'Player')
    # Schema-only databases (including migration tests after a flush) have no
    # release identities to curate. Production bootstrap separately requires
    # the complete player pack; a partially missing pack still fails below.
    if not Player.objects.using(alias).exists():
        return
    required = {slug for b in source['boards'] for s in b['slots'] for slug in s['audited_candidates']}
    if set(Player.objects.using(alias).filter(slug__in=required).values_list('slug', flat=True)) != required:
        raise ValueError('Playoff board candidate identities are missing')
    with transaction.atomic(using=alias):
        for definition in source['boards']:
            day = date.fromisoformat(definition['date'])
            previous = Daily.objects.using(alias).select_for_update().filter(date=day, is_current=True).first()
            if previous and previous.locale_seed == definition['locale_seed']:
                continue
            if previous:
                # All old slots, attempts, answers, comments and scores retain
                # their original board ID. New play starts on a fresh ID.
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
    dependencies = [
        ('dailies', '0023_daily_revisions'),
        ('players', '0006_verified_career_roles'),
    ]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
