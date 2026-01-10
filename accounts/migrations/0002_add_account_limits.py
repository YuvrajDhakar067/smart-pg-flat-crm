# Generated manually to add per-account limits

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='max_managers',
            field=models.IntegerField(blank=True, help_text='Maximum number of managers for this account. Leave blank to use site default. Set to 0 for unlimited.', null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name='account',
            name='max_properties',
            field=models.IntegerField(blank=True, help_text='Maximum number of properties (buildings) for this account. Leave blank to use site default. Set to 0 for unlimited.', null=True, validators=[django.core.validators.MinValueValidator(0)]),
        ),
    ]
