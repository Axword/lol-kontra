from django.db import migrations, models


def clarify_debut(apps, schema_editor):
    # Only the wording changes; condition IDs, requirements and games stay intact.
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    Condition.objects.using(schema_editor.connection.alias).filter(condition_type='worlds_title_on_debut').update(
        label_pl='Wygrał Worlds będąc debiutantem turnieju',
        label_en='Won Worlds on his first appearance at the tournament',
    )


class Migration(migrations.Migration):
    dependencies = [('dailies', '0014_upcoming_precise_boards')]
    operations = [
        migrations.AddField(model_name='daily', name='minimum_candidates',
                            field=models.PositiveSmallIntegerField(null=True, editable=False)),
        migrations.AlterField(model_name='daily', name='minimum_candidates',
                              field=models.PositiveSmallIntegerField(default=10, null=True, editable=False)),
        migrations.RunPython(clarify_debut, migrations.RunPython.noop),
    ]
