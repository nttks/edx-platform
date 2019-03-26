# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0006_contractoption_send_submission_reminder'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractoption',
            name='auto_register_students_flg',
            field=models.BooleanField(default=False),
        ),
    ]
