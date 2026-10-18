from collections import Counter

from django.db import migrations, models


def update_display_rarity(apps, schema_editor):
    """Relabel saved percentages without rescoring or changing game progress."""
    alias = schema_editor.connection.alias
    Config = apps.get_model('scoring', 'ScoringConfig')
    Snapshot = apps.get_model('scoring', 'AnswerStatsDaily')
    Answer = apps.get_model('submissions', 'SubmissionAnswer')
    Submission = apps.get_model('submissions', 'Submission')
    UserStats = apps.get_model('users', 'UserStats')
    Config.objects.using(alias).filter(is_active=True).update(
        threshold_rare=15.0, threshold_epic=5.0, threshold_legendary=2.0,
    )

    def tier_for(field):
        return models.Case(
            models.When(**{f'{field}__lt': 2.0}, then=models.Value('legendary')),
            models.When(**{f'{field}__lt': 5.0}, then=models.Value('epic')),
            models.When(**{f'{field}__lt': 15.0}, then=models.Value('rare')),
            default=models.Value('common'), output_field=models.CharField(),
        )

    Snapshot.objects.using(alias).filter(is_correct=True).update(rarity_tier=tier_for('pick_percent'))
    Answer.objects.using(alias).filter(is_correct=True, rarity_percent__isnull=False).update(
        rarity_tier=tier_for('rarity_percent'),
    )

    # Keep the derived rarity counter consistent. Every score, streak, timestamp,
    # answer percentage and diamond flag is deliberately left untouched.
    games = Submission.objects.using(alias).filter(
        user__isnull=False, is_practice=False, is_seed=False,
    ).annotate(
        slot_count=models.Count('daily__slots', distinct=True),
        correct_count=models.Count('answers', filter=models.Q(answers__is_correct=True), distinct=True),
    ).filter(
        models.Q(is_scored=True) | models.Q(errors_used__gte=10)
        | models.Q(slot_count__gt=0, correct_count__gte=models.F('slot_count')),
    )
    counts = Counter(Answer.objects.using(alias).filter(
        submission_id__in=games.values('pk'), is_correct=True, rarity_tier='legendary',
    ).values_list('submission__user_id', flat=True))
    UserStats.objects.using(alias).all().update(legendary_answers=0)
    for user_id, count in counts.items():
        UserStats.objects.using(alias).filter(user_id=user_id).update(legendary_answers=count)


class Migration(migrations.Migration):
    dependencies = [
        ('scoring', '0003_integrity_constraints'),
        ('dailies', '0009_october_2026_release'),
        ('users', '0003_integrity_constraints'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scoringconfig', name='threshold_rare', field=models.FloatField(default=15.0),
        ),
        migrations.AlterField(
            model_name='scoringconfig', name='threshold_epic', field=models.FloatField(default=5.0),
        ),
        migrations.AlterField(
            model_name='scoringconfig', name='threshold_legendary', field=models.FloatField(default=2.0),
        ),
        migrations.RunPython(update_display_rarity, migrations.RunPython.noop),
    ]
