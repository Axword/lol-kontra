from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('submissions', '0001_initial'),
    ]

    operations = [
        # total_points: IntegerField → FloatField (no more *10 encoding)
        migrations.AlterField(
            model_name='submission',
            name='total_points',
            field=models.FloatField(default=0),
        ),
        # is_scored: add db_index
        migrations.AlterField(
            model_name='submission',
            name='is_scored',
            field=models.BooleanField(default=False, db_index=True),
        ),
        # points_awarded: IntegerField → FloatField (fixes decimal truncation)
        migrations.AlterField(
            model_name='submissionanswer',
            name='points_awarded',
            field=models.FloatField(default=0),
        ),
        # is_correct: add db_index
        migrations.AlterField(
            model_name='submissionanswer',
            name='is_correct',
            field=models.BooleanField(default=False, db_index=True),
        ),
        # is_diamond_pick: add db_index
        migrations.AlterField(
            model_name='submissionanswer',
            name='is_diamond_pick',
            field=models.BooleanField(default=False, db_index=True),
        ),
        # Add composite indexes
        migrations.AddIndex(
            model_name='submission',
            index=models.Index(fields=['daily', 'is_scored'], name='idx_submission_daily_scored'),
        ),
        migrations.AddIndex(
            model_name='submissionanswer',
            index=models.Index(fields=['daily_slot', 'is_correct'], name='idx_answer_slot_correct'),
        ),
        migrations.AddIndex(
            model_name='submissionanswer',
            index=models.Index(fields=['daily_slot', 'player'], name='idx_answer_slot_player'),
        ),
    ]
