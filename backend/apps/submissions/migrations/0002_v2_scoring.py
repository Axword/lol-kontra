"""
V2 punktacji:
  * points_awarded / total_points jako FloatField (wcześniej Integer – ucinał ułamki),
  * serwerowy licznik błędów (errors_used),
  * pełna historia prób (SubmissionAttempt).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0001_initial'),
        ('dailies', '0003_alter_daily_reveal_mode'),
        ('players', '0002_alter_player_continent_alter_player_country_code_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='submissionanswer',
            name='points_awarded',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='submission',
            name='total_points',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='submission',
            name='errors_used',
            field=models.IntegerField(default=0),
        ),
        migrations.CreateModel(
            name='SubmissionAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_correct', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('daily_slot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='dailies.dailyslot')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='players.player')),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='submissions.submission')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.AddIndex(
            model_name='submissionattempt',
            index=models.Index(fields=['submission', 'daily_slot'], name='submissions_sub_slot_idx'),
        ),
        # Wyniki policzone starym modelem (500 minus odjęcia) są nieporównywalne
        # z nowym – kasujemy je, nocny score_daily policzy wszystko od nowa.
        migrations.RunSQL(
            sql="UPDATE submissions_submission SET total_points = 0, is_scored = false;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
