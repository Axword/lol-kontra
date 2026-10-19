"""Add birthplace geography without changing historical eligibility."""
from django.db import migrations, models


LEGACY_LABELS = (
    ('Europe', 'Europejczyk', 'European',
     'Narodowość: kraj w Europie', 'Nationality: European country'),
    ('North America', 'Z Ameryki Północnej', 'North American',
     'Narodowość: kraj w Ameryce Północnej', 'Nationality: North American country'),
)


def clarify_legacy_labels(apps, schema_editor):
    Condition = apps.get_model('dailies', 'DailySlotCondition')
    database = schema_editor.connection.alias
    for value, old_pl, old_en, new_pl, new_en in LEGACY_LABELS:
        matching = Condition.objects.using(database).filter(
            condition_type='continent', operator='eq', value=value,
        )
        # Match each language independently: a custom translation is never
        # replaced merely because the other language still has an auto label.
        matching.filter(label_pl=old_pl).update(label_pl=new_pl)
        matching.filter(label_en=old_en).update(label_en=new_en)


class Migration(migrations.Migration):
    dependencies = [('dailies', '0010_daily_community')]
    operations = [
        migrations.AlterField(
            model_name='dailyslotcondition', name='condition_type',
            field=models.CharField(choices=[("role", "Rola"), ("region", "Region"), ("residency", "Residency"), ("country", "Kraj"), ("continent", "Kontynent"), ("birth_continent", "Kontynent urodzenia"), ("team", "Drużyna"), ("team_year", "Drużyna w konkretnym roku"), ("league", "Liga"), ("coach", "Trener"), ("active", "Aktywny / emerytowany"), ("birth_year_range", "Rok urodzenia"), ("champion_played", "Grał championem"), ("worlds_appearance", "Występ na Worlds"), ("worlds_count_min", "Min. liczba występów na Worlds"), ("worlds_debut_year", "Debiut na Worlds"), ("worlds_last_year", "Ostatni Worlds"), ("worlds_early_era", "Worlds w erze S1-S3"), ("worlds_teams_min", "Min. liczba organizacji na Worlds"), ("worlds_multi_role", "Worlds na kilku rolach"), ("worlds_champion", "Mistrz Worlds"), ("worlds_titles_min", "Min. liczba tytułów Worlds"), ("worlds_final", "Finał Worlds"), ("worlds_final_lost", "Przegrany finał Worlds"), ("worlds_semifinal", "Półfinał Worlds"), ("worlds_group_escape", "Wyjście z grupy"), ("worlds_never_escaped", "Nigdy nie wyszedł z grupy"), ("worlds_never_won", "Nigdy nie wygrał Worlds"), ("worlds_playin", "Przeszedł play-in"), ("pentakill_worlds", "Pentakill na Worlds"), ("worlds_win_rate", "Win rate na Worlds"), ("worlds_games", "Liczba meczów na Worlds"), ("worlds_top5_champion", "Champion w top 5 na Worlds"), ("career_top5_champion", "Champion w top 5 kariery"), ("worlds_eliminated_stage", "Etap odpadnięcia z Worlds"), ("msi_appearance", "Występ na MSI"), ("leagues_min", "Min. liczba lig głównych"), ("wildcard_region", "Region wildcard"), ("import_player", "Import (gra poza swoim regionem)")], max_length=32),
        ),
        # Keeping the clearer labels on rollback avoids overwriting an author's
        # later custom label that happens to match the new wording.
        migrations.RunPython(clarify_legacy_labels, migrations.RunPython.noop),
    ]
