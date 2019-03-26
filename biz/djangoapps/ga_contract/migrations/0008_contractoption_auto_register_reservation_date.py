# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0007_contractoption_auto_register_students_flg'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractoption',
            name='auto_register_reservation_date',
            field=models.DateField(default=None, null=True),
        ),
    ]
