# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('gx_member', '0004_auto_20180719_1104'),
    ]

    operations = [
        migrations.AlterField(
            model_name='member',
            name='code',
            field=models.CharField(max_length=255, null=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='member',
            name='created',
            field=models.DateTimeField(default=datetime.datetime(2018, 12, 11, 14, 29, 16, 741052), db_index=True),
        ),
    ]
