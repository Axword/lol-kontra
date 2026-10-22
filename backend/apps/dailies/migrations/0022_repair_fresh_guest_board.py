"""Install the guest board after the old synthetic calendar votes are removed.

On an existing installation those votes were already gone when 0013 ran. A fresh
database can run that migration before scoring.0005, so its preservation guard
correctly skips the seeded board. Repair only the untouched default board here.
"""
from django.db import migrations
from ._guest_board_2026 import install_board, load_release


def install(apps, schema_editor):
    alias = schema_editor.connection.alias
    Daily = apps.get_model('dailies', 'Daily')
    board = load_release()['board']
    daily = Daily.objects.using(alias).select_for_update().filter(date=board['date']).first()
    if daily is None or daily.author_name.strip():
        return
    # install_board independently protects every started game, including an
    # unfinished game with no answers yet. Do not weaken that protection.
    install_board(apps, alias, board)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [
        ('dailies', '0021_activity_future_boards'),
        ('scoring', '0007_sum_pick_percentages'),
    ]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
