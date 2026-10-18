from collections import Counter

from django.db import migrations, models


def install_first_pick_metadata(apps, schema_editor):
    """Change display/first-pick metadata, never earned points or game progress."""
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    Slot = apps.get_model('dailies', 'DailySlot')
    Game = apps.get_model('submissions', 'Submission')
    Answer = apps.get_model('submissions', 'SubmissionAnswer')
    Attempt = apps.get_model('submissions', 'SubmissionAttempt')
    Snapshot = apps.get_model('scoring', 'AnswerStatsDaily')
    Config = apps.get_model('scoring', 'ScoringConfig')
    UserStats = apps.get_model('users', 'UserStats')
    list(Daily.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    list(Slot.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    list(Game.objects.using(alias).select_for_update().order_by('pk').values_list('pk', flat=True))
    Config.objects.using(alias).filter(is_active=True).update(
        threshold_uncommon=25, threshold_rare=15, threshold_epic=5, threshold_legendary=2,
    )
    # Inactive legacy configurations can have rare thresholds above25. Preserve
    # their old values while giving the new upper bound a valid ordered value.
    Config.objects.using(alias).filter(threshold_uncommon__lt=models.F('threshold_rare')).update(
        threshold_uncommon=models.F('threshold_rare'),
    )

    def tiers(field):
        return models.Case(
            models.When(**{f'{field}__lt': 2}, then=models.Value('legendary')),
            models.When(**{f'{field}__lt': 5}, then=models.Value('epic')),
            models.When(**{f'{field}__lt': 15}, then=models.Value('rare')),
            models.When(**{f'{field}__lt': 25}, then=models.Value('uncommon')),
            default=models.Value('common'), output_field=models.CharField(),
        )
    Answer.objects.using(alias).filter(is_correct=True, rarity_percent__isnull=False).update(
        rarity_tier=tiers('rarity_percent'),
    )
    Snapshot.objects.using(alias).filter(is_correct=True).update(rarity_tier=tiers('pick_percent'))

    successes = {}
    for attempt in Attempt.objects.using(alias).filter(
        is_correct=True, submission__is_seed=False, submission__is_practice=False,
    ).order_by('created_at', 'pk').iterator():
        successes.setdefault((attempt.submission_id, attempt.daily_slot_id, attempt.player_id),
                             (attempt.created_at, attempt.pk))
    winners = {}
    for answer in Answer.objects.using(alias).filter(
        is_correct=True, submission__is_seed=False, submission__is_practice=False,
    ).select_related('submission').order_by('pk'):
        event = successes.get((answer.submission_id, answer.daily_slot_id, answer.player_id),
                              (answer.submission.submitted_at, answer.pk))
        order = (*event, answer.pk)
        pair = (answer.daily_slot_id, answer.player_id)
        if pair not in winners or order < winners[pair][0]:
            winners[pair] = (order, answer, event[0])
    Answer.objects.using(alias).filter(
        models.Q(is_diamond_pick=True) | models.Q(diamond_awarded_at__isnull=False),
    ).update(is_diamond_pick=False, diamond_awarded_at=None)
    awarded = []
    for _, answer, awarded_at in winners.values():
        answer.is_diamond_pick = True
        answer.diamond_awarded_at = awarded_at
        awarded.append(answer)
    Answer.objects.using(alias).bulk_update(awarded, ['is_diamond_pick', 'diamond_awarded_at'])

    finished = Game.objects.using(alias).filter(
        is_seed=False, is_practice=False, user__isnull=False,
    ).annotate(
        slot_count=models.Count('daily__slots', distinct=True),
        correct_count=models.Count('answers', filter=models.Q(answers__is_correct=True), distinct=True),
    ).filter(models.Q(is_scored=True) | models.Q(errors_used__gte=10)
             | models.Q(slot_count__gt=0, correct_count__gte=models.F('slot_count')))
    counts = Counter(Answer.objects.using(alias).filter(
        submission_id__in=finished.values('pk'), is_correct=True, is_diamond_pick=True,
    ).values_list('submission__user_id', flat=True))
    UserStats.objects.using(alias).all().update(diamond_picks=0)
    for user_id, count in counts.items():
        UserStats.objects.using(alias).filter(user_id=user_id).update(diamond_picks=count)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ('scoring', '0005_remove_synthetic_votes'),
        ('submissions', '0006_uncommon_rarity'),
    ]
    operations = [
        migrations.RemoveConstraint(model_name='scoringconfig', name='scoring_thresholds_ordered'),
        migrations.AddField(model_name='scoringconfig', name='threshold_uncommon', field=models.FloatField(default=25.0, db_default=25.0)),
        migrations.RunPython(install_first_pick_metadata, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='scoringconfig', constraint=models.CheckConstraint(
            name='scoring_thresholds_ordered', check=(
                models.Q(threshold_legendary__gte=0, threshold_legendary__lte=models.F('threshold_epic'))
                & models.Q(threshold_epic__lte=models.F('threshold_rare'), threshold_rare__lte=models.F('threshold_uncommon'))
                & models.Q(threshold_uncommon__lte=100)
            ),
        )),
    ]
