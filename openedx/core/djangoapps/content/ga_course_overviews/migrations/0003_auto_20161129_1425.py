# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_course_overviews', '0002_auto_20161018_1117'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseoverviewextra',
            name='individual_end_days',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='individual_end_hours',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='individual_end_minutes',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='self_paced',
            field=models.BooleanField(default=False),
        ),
    ]
