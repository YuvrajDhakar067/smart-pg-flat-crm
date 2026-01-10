# Generated manually to add image and video_url fields to ContentBlock

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0003_auto_20260110_1951'),
    ]

    operations = [
        migrations.AddField(
            model_name='contentblock',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='content_blocks/'),
        ),
        migrations.AddField(
            model_name='contentblock',
            name='video_url',
            field=models.URLField(blank=True),
        ),
        migrations.AlterField(
            model_name='contentblock',
            name='block_type',
            field=models.CharField(choices=[('text', 'Text'), ('html', 'HTML'), ('image', 'Image'), ('video', 'Video')], default='text', max_length=20),
        ),
        migrations.AlterField(
            model_name='contentblock',
            name='key',
            field=models.SlugField(help_text='Unique identifier for this content block', unique=True),
        ),
    ]
