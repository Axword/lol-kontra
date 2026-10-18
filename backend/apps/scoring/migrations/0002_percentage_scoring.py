from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [('scoring', '0001_initial')]

    operations = [
        migrations.RemoveField(model_name='scoringconfig', name='points_common'),
        migrations.RemoveField(model_name='scoringconfig', name='points_rare'),
        migrations.RemoveField(model_name='scoringconfig', name='points_epic'),
        migrations.RemoveField(model_name='scoringconfig', name='points_legendary'),
        migrations.RemoveField(model_name='scoringconfig', name='diamond_bonus'),
    ]
