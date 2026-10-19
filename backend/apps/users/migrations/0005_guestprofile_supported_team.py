from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('users', '0004_guestprofile')]

    operations = [
        migrations.AddField(
            model_name='guestprofile',
            name='supported_team',
            field=models.CharField(blank=True, db_default='', default='', max_length=16),
        ),
        migrations.AddConstraint(
            model_name='guestprofile',
            constraint=models.CheckConstraint(
                check=models.Q(supported_team='') | models.Q(supported_team__in=(
                    'al', 'blg', 'tes', 'ig', 'gen', 'hle', 't1', 'dk', 'g2',
                    'mkoi', 'kc', 'tlaw', 'lyon', 'c9', 'tsw', 'cfo', 'mvk', 'los', 'fur',
                )),
                name='guestprofile_supported_team_valid',
            ),
        ),
    ]
