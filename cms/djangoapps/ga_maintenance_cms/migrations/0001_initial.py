# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='MaintenanceMessage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.TextField(null=True, blank=True)),
                ('display_order', models.IntegerField(default=1)),
                ('display_flg', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['-display_order'],
            },
        ),
    ]
