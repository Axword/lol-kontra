from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('submissions', '0005_integrity_constraints')]
    operations = [migrations.AlterField(
        model_name='submissionanswer', name='rarity_tier',
        field=models.CharField(blank=True, null=True, max_length=16, choices=[
            ('common', 'Common'), ('uncommon', 'Uncommon'), ('rare', 'Rare'),
            ('epic', 'Epic'), ('legendary', 'Legendary'),
        ]),
    )]
