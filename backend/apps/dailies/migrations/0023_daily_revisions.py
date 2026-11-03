from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('dailies', '0022_repair_fresh_guest_board')]
    operations = [
        migrations.AddField(
            model_name='daily', name='is_current',
            field=models.BooleanField(default=True, db_default=True, editable=False),
        ),
        migrations.AlterField(
            model_name='daily', name='date', field=models.DateField(db_index=True),
        ),
        migrations.AddConstraint(
            model_name='daily', constraint=models.UniqueConstraint(
                fields=['date'], condition=models.Q(is_current=True), name='daily_one_current_per_date',
            ),
        ),
    ]
