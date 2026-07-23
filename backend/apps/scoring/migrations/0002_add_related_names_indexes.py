from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dailies', '0003_alter_daily_reveal_mode'),
        ('players', '0003_team_enhancements_career_champion_stat'),
        ('scoring', '0001_initial'),
    ]

    operations = [
        # Add related_name and db_index to daily_slot FK
        migrations.AlterField(
            model_name='answerstatsdaily',
            name='daily_slot',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='answer_stats',
                to='dailies.dailyslot',
                db_index=True,
            ),
        ),
        # Add related_name to player FK
        migrations.AlterField(
            model_name='answerstatsdaily',
            name='player',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='answer_stats',
                to='players.player',
            ),
        ),
        # Add index for fast lookups by daily_slot
        migrations.AddIndex(
            model_name='answerstatsdaily',
            index=models.Index(fields=['daily_slot'], name='idx_stats_slot'),
        ),
    ]
