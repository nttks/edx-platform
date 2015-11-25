# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userstanding',
            name='resign_reason',
            field=models.TextField(max_length=1000, null=True),
        ),
    ]
