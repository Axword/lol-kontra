"""Install reviewed future boards; never touch a started or guest-authored board."""
import hashlib
import json
from pathlib import Path
from django.db import migrations, transaction

SOURCE = 'worlds_editorial_2026_10_21_v1.json'
SHA256 = 'd901b6d9b9facc6adba5be928d94ae23c4bdc22e7a62fda03658d1be2e1cd45f'


def install(apps, schema_editor):
    payload = (Path(__file__).resolve().parents[1] / 'fixtures' / 'releases' / SOURCE).read_text(encoding='utf-8').encode()
    if hashlib.sha256(payload).hexdigest() != SHA256:
        raise ValueError('Future board source checksum mismatch')
    Daily = apps.get_model('dailies', 'Daily')
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Submission = apps.get_model('submissions', 'Submission')
    alias = schema_editor.connection.alias
    with transaction.atomic(using=alias):
        for row in json.loads(payload):
            daily = Daily.objects.using(alias).select_for_update().filter(date=row['date'],author_name='').first()
            if not daily or Submission.objects.using(alias).filter(daily_id=daily.pk).exists():
                continue
            if row['date'] < '2026-10-21':
                raise ValueError('Future editorial release contains an archived date')
            slots = {slot.role:slot for slot in daily.slots.using(alias).all()}
            if set(slots) != {'top','jungle','mid','adc','support'}:
                raise ValueError('Future board has incomplete positions')
            unchanged = daily.minimum_candidates == 10 and all(
                list(Condition.objects.using(alias).filter(slot_id=slots[s['role']].pk)
                     .order_by('order', 'pk').values('condition_type','operator','value','label_pl','label_en','order')) == s['conditions']
                for s in row['slots']
            )
            if unchanged:
                continue
            for slot_data in row['slots']:
                slot = slots[slot_data['role']]
                Condition.objects.using(alias).filter(slot_id=slot.pk).delete()
                Condition.objects.using(alias).bulk_create([Condition(slot_id=slot.pk,**condition) for condition in slot_data['conditions']])
            Daily.objects.using(alias).filter(pk=daily.pk).update(minimum_candidates=10)


class Migration(migrations.Migration):
    dependencies = [('dailies','0019_clarify_lta_conferences'),('submissions','0007_infinityrun_infinityattempt_and_more')]
    operations = [migrations.RunPython(install,migrations.RunPython.noop)]
