from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0003_integrity_constraints')]

    operations = [
        migrations.CreateModel(
            name='GuestProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guest_key', models.CharField(editable=False, max_length=64, unique=True)),
                ('nickname', models.CharField(blank=True, default='', max_length=24)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'constraints': [models.CheckConstraint(check=models.Q(guest_key__regex=r'^[a-f0-9]{64}$'), name='guestprofile_key_is_sha256')]},
        ),
    ]
