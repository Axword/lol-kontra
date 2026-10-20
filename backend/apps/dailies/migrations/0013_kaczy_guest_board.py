from django.db import migrations

from ._guest_board_2026 import install


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ('dailies', '0012_precise_guest_conditions'),
        ('players', '0006_verified_career_roles'),
        ('submissions', '0006_uncommon_rarity'),
    ]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
