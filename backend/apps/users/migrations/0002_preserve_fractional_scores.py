from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0001_initial')]

    operations = [
        migrations.AlterField(model_name='userstats', name='total_points', field=models.FloatField(default=0)),
        migrations.AlterField(model_name='userstats', name='best_score', field=models.FloatField(default=0)),
    ]
