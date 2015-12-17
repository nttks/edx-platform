# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_overviews', '0005_delete_courseoverviewgeneratedhistory'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseoverview',
            name='is_course_hidden',
            field=models.BooleanField(default=False),
        ),
    ]
