# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_course_overviews', '0003_auto_20161129_1425'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseoverviewextra',
            name='custom_logo',
            field=models.TextField(default=b'', blank=True),
        ),
    ]
