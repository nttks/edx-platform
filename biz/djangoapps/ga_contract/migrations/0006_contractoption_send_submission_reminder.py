# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0005_contractoption'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractoption',
            name='send_submission_reminder',
            field=models.BooleanField(default=False),
        ),
    ]
