"""Retire marked test votes while preserving every historical human result."""
from collections import Counter

from django.db import migrations
from django.db.models import Count


def remove_synthetic_votes(apps, schema_editor):
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Submission = apps.get_model('submissions', 'Submission')
    Answer = apps.get_model('submissions', 'SubmissionAnswer')
    Snapshot = apps.get_model('scoring', 'AnswerStatsDaily')

    # Follow gameplay's board -> slot -> submission locking order. No active
    # request can append a choice halfway through this atomic cleanup.
    list(Daily.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    slots = list(Slot.objects.using(alias).select_for_update().order_by('pk').values_list('pk', 'daily_id'))
    list(Submission.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    affected = set(Submission.objects.using(alias).filter(is_seed=True).values_list('daily_id', flat=True))
    if not affected:
        return

    # Only the explicit marker permits deletion. Never infer synthetic data from
    # a guest token, nickname, chosen player or role. All human submissions,
    # answers, attempts, scoring fields and user statistics remain untouched.
    Submission.objects.using(alias).filter(is_seed=True).delete()

    affected_slots = {slot_id for slot_id, daily_id in slots if daily_id in affected}
    counts = list(Answer.objects.using(alias).filter(
        daily_slot_id__in=affected_slots, is_correct=True,
        submission__is_practice=False, submission__is_seed=False,
    ).values('daily_slot_id', 'player_id').annotate(pick_count=Count('id')))
    totals = Counter()
    for row in counts:
        totals[row['daily_slot_id']] += row['pick_count']

    snapshots = []
    for row in counts:
        percent = row['pick_count'] / totals[row['daily_slot_id']] * 100
        tier = 'legendary' if percent < 2 else 'epic' if percent < 5 else 'rare' if percent < 15 else 'common'
        snapshots.append(Snapshot(
            daily_slot_id=row['daily_slot_id'], player_id=row['player_id'],
            pick_count=row['pick_count'], pick_percent=percent, rarity_tier=tier, is_correct=True,
        ))
    Snapshot.objects.using(alias).filter(daily_slot_id__in=affected_slots).delete()
    Snapshot.objects.using(alias).bulk_create(snapshots)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [('scoring', '0004_display_rarity_thresholds')]
    operations = [migrations.RunPython(remove_synthetic_votes, migrations.RunPython.noop)]
