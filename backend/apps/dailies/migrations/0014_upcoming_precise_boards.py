from django.db import migrations

from ._upcoming_october_2026 import install


class Migration(migrations.Migration):
    atomic = True
    dependencies = [('dailies', '0013_kaczy_guest_board')]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
