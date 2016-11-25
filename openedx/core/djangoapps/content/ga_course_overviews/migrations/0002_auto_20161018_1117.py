# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_course_overviews', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='courseoverviewextra',
            name='has_terminated',
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='is_course_hidden',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='terminate_start',
            field=models.DateTimeField(null=True),
        ),
    ]
