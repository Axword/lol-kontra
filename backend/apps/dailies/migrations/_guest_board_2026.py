"""Frozen, source-backed guest board. Does not rewrite games already started."""
from datetime import date
import hashlib
import json
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent / 'fixtures/releases/guest_board_2026_10_22_v1.json'
SHA256 = '183c30cc56397a7e41924f5fe1afc4ab2b35cfc2ae86e187a4189889c64b4956'


def load_release():
    raw = SOURCE.read_text(encoding='utf-8').encode('utf-8')
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Guest board release SHA-256 mismatch')
    return json.loads(raw)


def install(apps, schema_editor):
    alias = schema_editor.connection.alias
    source = load_release()
    Player = apps.get_model('players', 'Player')
    for row in source['players']:
        player = Player.objects.using(alias).select_for_update().filter(slug=row['slug']).first()
        if player is None:
            raise ValueError(f"Missing released player: {row['slug']}")
        attributes = {**player.attributes, **row['attributes']}
        Player.objects.using(alias).filter(pk=player.pk).update(attributes=attributes)
    install_board(apps, alias, source['board'])


def install_board(apps, alias, spec):
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Submission = apps.get_model('submissions', 'Submission')
    daily, _ = Daily.objects.using(alias).select_for_update().get_or_create(date=date.fromisoformat(spec['date']))
    if Submission.objects.using(alias).filter(daily_id=daily.pk).exists():
        return
    author = {key: spec[key] for key in ('author_name', 'author_url', 'author_description') if key in spec}
    Daily.objects.using(alias).filter(pk=daily.pk).update(status='published', **author)
    existing = list(Slot.objects.using(alias).filter(daily_id=daily.pk).order_by('position'))
    if existing and [s.role for s in existing] != [s['role'] for s in spec['slots']]:
        raise ValueError('Unexpected released board role order')
    for position, definition in enumerate(spec['slots'], 1):
        slot, _ = Slot.objects.using(alias).get_or_create(daily_id=daily.pk, position=position,
            defaults={'role': definition['role'], 'label_pl': definition['role'], 'label_en': definition['role']})
        fields = ('condition_type', 'operator', 'value', 'label_pl', 'label_en')
        current = list(Condition.objects.using(alias).filter(slot_id=slot.pk).order_by('order', 'pk').values(*fields))
        if current == definition['conditions']:
            continue
        Condition.objects.using(alias).filter(slot_id=slot.pk).delete()
        for order, requirement in enumerate(definition['conditions']):
            Condition.objects.using(alias).create(slot_id=slot.pk, order=order, **requirement)
