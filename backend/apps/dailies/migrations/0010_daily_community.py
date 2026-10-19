import uuid

from django.core.validators import MaxLengthValidator
from django.db import migrations, models
from django.db.models.lookups import LessThanOrEqual
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('dailies', '0009_october_2026_release'),
        ('submissions', '0006_uncommon_rarity'),
    ]

    operations = [
        migrations.AddField('daily', 'author_name', models.CharField(blank=True, db_default='', default='', max_length=64)),
        migrations.AddField('daily', 'author_url', models.URLField(blank=True, db_default='', default='')),
        migrations.AddField('daily', 'author_description', models.CharField(blank=True, db_default='', default='', max_length=180)),
        migrations.CreateModel(
            name='CommunityComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(blank=True, default='', max_length=500)),
                ('share_key', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('roster_png', models.BinaryField(validators=[MaxLengthValidator(256000)])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('submission', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                   related_name='community_comment', to='submissions.submission')),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
                'constraints': [models.CheckConstraint(
                    check=LessThanOrEqual(models.Func('roster_png', function='octet_length',
                                                      output_field=models.IntegerField()), models.Value(256000)),
                    name='community_png_bounded',
                )],
            },
        ),
    ]
