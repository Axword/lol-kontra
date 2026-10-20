from django.db import migrations
from ._minimum_ten_boards import install


class Migration(migrations.Migration):
    atomic = True
    dependencies = [('dailies', '0015_candidate_policy')]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
