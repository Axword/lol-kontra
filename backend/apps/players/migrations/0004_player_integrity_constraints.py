import django.db.models.lookups
from django.db import migrations, models


def check_existing_rows(apps, schema_editor):
    """Reject legacy violations explicitly; never repair/delete user data."""
    for operation in Migration.operations:
        if isinstance(operation, migrations.AddConstraint):
            model = apps.get_model('players', operation.model_name)
            invalid = list(model.objects.using(schema_editor.connection.alias)
                           .exclude(operation.constraint.check).values_list('pk', flat=True)[:6])
            if invalid:
                raise ValueError(f'Cannot add {operation.constraint.name}; invalid existing IDs: {invalid}')


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0003_release_worlds_players'),
    ]

    operations = [
        migrations.RunPython(check_existing_rows, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=models.Q(('worlds_count__gte', 0)), name='player_worlds_count_gte0'),
        ),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=models.Q(('worlds_titles_count__gte', 0)), name='player_titles_count_gte0'),
        ),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=models.Q(('primary_role__in', ['top', 'jungle', 'mid', 'adc', 'support'])), name='player_role_valid'),
        ),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=models.Q(('secondary_roles__contained_by', ['top', 'jungle', 'mid', 'adc', 'support'])), name='player_secondary_roles_valid'),
        ),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=models.Q(('birth_year__isnull', True), ('birth_year__range', (1900, 2100)), _connector='OR'), name='player_birth_year_valid'),
        ),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(models.Func('attributes', function='jsonb_typeof', output_field=models.CharField()), models.Value('object')), name='player_attributes_object'),
        ),
        migrations.AddConstraint(
            model_name='player',
            constraint=models.CheckConstraint(check=django.db.models.lookups.Exact(models.Func('career_stats', function='jsonb_typeof', output_field=models.CharField()), models.Value('object')), name='player_career_stats_object'),
        ),
        migrations.AddConstraint(
            model_name='playercoachhistory',
            constraint=models.CheckConstraint(check=models.Q(('year__isnull', True), ('year__range', (2000, 2100)), _connector='OR'), name='player_coach_year_valid'),
        ),
        migrations.AddConstraint(
            model_name='playerteamhistory',
            constraint=models.CheckConstraint(check=models.Q(('start_date__isnull', True), ('end_date__isnull', True), ('end_date__gte', models.F('start_date')), _connector='OR'), name='player_team_dates_ordered'),
        ),
        migrations.AddConstraint(
            model_name='playerteamhistory',
            constraint=models.CheckConstraint(check=models.Q(('role__in', ['', 'top', 'jungle', 'mid', 'adc', 'support'])), name='player_team_role_valid'),
        ),
        migrations.AddConstraint(
            model_name='tournamentappearance',
            constraint=models.CheckConstraint(check=models.Q(('year__range', (2000, 2100))), name='appearance_year_valid'),
        ),
        migrations.AddConstraint(
            model_name='tournamentappearance',
            constraint=models.CheckConstraint(check=models.Q(('placement__isnull', True), ('placement__gte', 1), _connector='OR'), name='appearance_placement_positive'),
        ),
        migrations.AddConstraint(
            model_name='tournamentappearance',
            constraint=models.CheckConstraint(check=models.Q(('role__in', ['', 'top', 'jungle', 'mid', 'adc', 'support'])), name='appearance_role_valid'),
        ),
    ]
