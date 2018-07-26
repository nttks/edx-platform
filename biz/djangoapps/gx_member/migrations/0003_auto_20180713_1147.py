# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('gx_member', '0002_auto_20180621_1207'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='member',
            unique_together=set([('org', 'user', 'is_active', 'is_delete')]),
        ),
    ]
