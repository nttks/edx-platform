# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('gx_member', '0003_auto_20180713_1147'),
    ]

    operations = [
        migrations.AlterField(
            model_name='membertaskhistory',
            name='updated',
            field=models.DateTimeField(null=True),
        ),
    ]
