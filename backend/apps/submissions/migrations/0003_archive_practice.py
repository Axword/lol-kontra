from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('submissions', '0002_v2_scoring')]

    operations = [
        migrations.AddField(model_name='submission', name='is_practice', field=models.BooleanField(default=False)),
        migrations.RemoveConstraint(model_name='submission', name='uniq_daily_user'),
        migrations.RemoveConstraint(model_name='submission', name='uniq_daily_guest'),
        migrations.AddConstraint(model_name='submission', constraint=models.UniqueConstraint(
            fields=['daily', 'user', 'is_practice'], condition=models.Q(user__isnull=False), name='uniq_daily_user_mode')),
        migrations.AddConstraint(model_name='submission', constraint=models.UniqueConstraint(
            fields=['daily', 'guest_token', 'is_practice'], condition=models.Q(guest_token__isnull=False), name='uniq_daily_guest_mode')),
    ]
