from django.db import migrations


def clarify_lta_conferences(apps, schema_editor):
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    clues = Condition.objects.using(schema_editor.connection.alias).filter(
        condition_type='leagues_min', operator='gte', value=2,
    )
    clues.filter(label_pl='Grał w min. 2 z lig: LCK, LPL, LEC, LCS, LTA').update(
        label_pl='Grał w min. 2 z lig: LCK, LPL, LEC, LCS, LTA, LTA North, LTA South',
    )
    clues.filter(label_en='Played in at least 2 of LCK, LPL, LEC, LCS, LTA').update(
        label_en='Played in at least 2 of LCK, LPL, LEC, LCS, LTA, LTA North, LTA South',
    )


class Migration(migrations.Migration):
    dependencies = [('dailies', '0018_clarify_default_clues')]
    operations = [migrations.RunPython(clarify_lta_conferences, migrations.RunPython.noop)]
