from django.db import migrations
from ._october_2026_release import install_calendar


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ('dailies', '0008_daily_integrity_constraints'),
        ('players', '0004_player_integrity_constraints'),
        ('submissions', '0005_integrity_constraints'),
        ('scoring', '0003_integrity_constraints'),
    ]
    operations = [migrations.RunPython(install_calendar, migrations.RunPython.noop)]
