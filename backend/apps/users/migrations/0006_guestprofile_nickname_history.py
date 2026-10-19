from django.db import migrations, models


def remember_existing_nicknames(apps, schema_editor):
    Profile = apps.get_model('users', 'GuestProfile')
    Profile.objects.using(schema_editor.connection.alias).exclude(nickname='').update(has_custom_nickname=True)


class Migration(migrations.Migration):
    dependencies = [('users', '0005_guestprofile_supported_team')]
    operations = [
        migrations.AddField(
            model_name='guestprofile', name='has_custom_nickname',
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.RunPython(remember_existing_nicknames, migrations.RunPython.noop),
    ]
