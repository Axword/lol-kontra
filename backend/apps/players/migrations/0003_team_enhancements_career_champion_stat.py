from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0002_alter_player_continent_alter_player_country_code_and_more'),
    ]

    operations = [
        # Team model enhancements
        migrations.AddField(
            model_name='team',
            name='is_active',
            field=models.BooleanField(default=True, db_index=True),
        ),
        migrations.AddField(
            model_name='team',
            name='is_worlds_champion',
            field=models.BooleanField(default=False, db_index=True,
                help_text='Czy drużyna kiedykolwiek wygrała Worlds'),
        ),
        migrations.AddField(
            model_name='team',
            name='worlds_titles_years',
            field=models.JSONField(default=list, blank=True,
                help_text='Lista lat, w których drużyna wygrała Worlds'),
        ),
        migrations.AddField(
            model_name='team',
            name='logo_url',
            field=models.URLField(max_length=512, blank=True, default=''),
        ),
        # CareerChampionStat model
        migrations.CreateModel(
            name='CareerChampionStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('champion_name', models.CharField(max_length=64, db_index=True)),
                ('games_played', models.IntegerField(default=0)),
                ('games_won', models.IntegerField(default=0)),
                ('games_lost', models.IntegerField(default=0)),
                ('win_ratio', models.FloatField(null=True, blank=True)),
                ('kills', models.FloatField(null=True, blank=True)),
                ('deaths', models.FloatField(null=True, blank=True)),
                ('assists', models.FloatField(null=True, blank=True)),
                ('kda', models.FloatField(null=True, blank=True)),
                ('cs_per_min', models.FloatField(null=True, blank=True)),
                ('dmg_per_min', models.FloatField(null=True, blank=True)),
                ('source', models.CharField(max_length=32, default='lolwiki', db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('player', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='champion_stats',
                    to='players.player',
                )),
            ],
            options={
                'ordering': ['-games_played'],
                'unique_together': {('player', 'champion_name', 'source')},
            },
        ),
        migrations.AddIndex(
            model_name='careerchampionstat',
            index=models.Index(fields=['player', '-games_played'], name='players_car_player__idx'),
        ),
        migrations.AddIndex(
            model_name='careerchampionstat',
            index=models.Index(fields=['champion_name'], name='players_car_champio_idx'),
        ),
    ]
