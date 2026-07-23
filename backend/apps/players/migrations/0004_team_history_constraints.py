from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0003_team_enhancements_career_champion_stat'),
    ]

    operations = [
        # Add related_name to team FK
        migrations.AlterField(
            model_name='playerteamhistory',
            name='team',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='player_histories',
                to='players.team',
            ),
        ),
        # Add unique_together constraint to prevent duplicates
        migrations.AlterUniqueTogether(
            name='playerteamhistory',
            unique_together={('player', 'team', 'start_date')},
        ),
        # Add default ordering
        migrations.AlterModelOptions(
            name='playerteamhistory',
            options={
                'ordering': ['-start_date'],
                'verbose_name_plural': 'Player team history',
            },
        ),
    ]
