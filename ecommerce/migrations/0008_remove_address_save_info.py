# Generated by Django 2.2.7 on 2020-04-05 20:23

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce', '0007_auto_20200405_0254'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='address',
            name='save_info',
        ),
    ]
