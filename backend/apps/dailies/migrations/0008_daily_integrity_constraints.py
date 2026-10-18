from django.conf import settings
from django.db import migrations, models


def check_existing_rows(apps, schema_editor):
    """Fail before adding checks instead of discarding malformed boards."""
    for operation in Migration.operations:
        if isinstance(operation, migrations.AddConstraint):
            model = apps.get_model('dailies', operation.model_name)
            invalid = list(model.objects.using(schema_editor.connection.alias)
                           .exclude(operation.constraint.check).values_list('pk', flat=True)[:6])
            if invalid:
                raise ValueError(f'Cannot add {operation.constraint.name}; invalid existing IDs: {invalid}')


class Migration(migrations.Migration):

    dependencies = [
        ('dailies', '0007_worlds_elimination_stage'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(check_existing_rows, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='daily',
            constraint=models.CheckConstraint(check=models.Q(('status__in', ['draft', 'published', 'closed', 'scored'])), name='daily_status_valid'),
        ),
        migrations.AddConstraint(
            model_name='daily',
            constraint=models.CheckConstraint(check=models.Q(('reveal_mode', 'instant')), name='daily_reveal_mode_valid'),
        ),
        migrations.AddConstraint(
            model_name='daily',
            constraint=models.CheckConstraint(check=models.Q(('published_at__isnull', True), ('closed_at__isnull', True), ('closed_at__gte', models.F('published_at')), _connector='OR'), name='daily_timestamps_ordered'),
        ),
        migrations.AddConstraint(
            model_name='dailyslot',
            constraint=models.CheckConstraint(check=models.Q(('position__range', (1, 5))), name='daily_slot_position_valid'),
        ),
        migrations.AddConstraint(
            model_name='dailyslot',
            constraint=models.CheckConstraint(check=models.Q(('role__in', ['top', 'jungle', 'mid', 'adc', 'support'])), name='daily_slot_role_valid'),
        ),
        migrations.AddConstraint(
            model_name='dailyslotcondition',
            constraint=models.CheckConstraint(check=models.Q(('operator__in', ['eq', 'in', 'gt', 'lt', 'gte', 'lte', 'any'])), name='daily_condition_operator_valid'),
        ),
        migrations.AddConstraint(
            model_name='dailyslotcondition',
            constraint=models.CheckConstraint(check=models.Q(('order__gte', 0)), name='daily_condition_order_gte0'),
        ),
    ]
