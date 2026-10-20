"""Refresh unstarted future boards after correcting competitive activity."""
import hashlib,json
from pathlib import Path
from django.db import migrations,transaction

SOURCE='activity_editorial_2026_10_23_v1.json'
SHA256='31f865c030161ada261e9990bf62be54102253a9ed1363a62e00c45a1e4c3de3'


def install(apps,schema_editor):
    payload=(Path(__file__).resolve().parents[1]/'fixtures'/'releases'/SOURCE).read_text(encoding='utf-8').encode()
    if hashlib.sha256(payload).hexdigest()!=SHA256:raise ValueError('Activity board checksum mismatch')
    Daily=apps.get_model('dailies','Daily');Condition=apps.get_model('dailies','DailySlotCondition')
    Submission=apps.get_model('submissions','Submission');alias=schema_editor.connection.alias
    with transaction.atomic(using=alias):
        for row in json.loads(payload):
            if row['date']<'2026-10-23':raise ValueError('Activity package contains an earlier board')
            daily=Daily.objects.using(alias).select_for_update().filter(date=row['date'],author_name='').first()
            if not daily or Submission.objects.using(alias).filter(daily_id=daily.pk).exists():continue
            slots={s.role:s for s in daily.slots.using(alias).all()}
            if set(slots)!={'top','jungle','mid','adc','support'}:raise ValueError('Incomplete activity board')
            for data in row['slots']:
                slot=slots[data['role']]
                current=list(Condition.objects.using(alias).filter(slot_id=slot.pk).order_by('order','pk').values(
                    'condition_type','operator','value','label_pl','label_en','order'))
                if current==data['conditions']:continue
                Condition.objects.using(alias).filter(slot_id=slot.pk).delete()
                Condition.objects.using(alias).bulk_create([Condition(slot_id=slot.pk,**c) for c in data['conditions']])
            Daily.objects.using(alias).filter(pk=daily.pk).update(minimum_candidates=10)


class Migration(migrations.Migration):
    dependencies=[('dailies','0020_worlds_focused_future_boards'),('submissions','0008_infinity_rank_snapshots')]
    operations=[migrations.RunPython(install,migrations.RunPython.noop)]
