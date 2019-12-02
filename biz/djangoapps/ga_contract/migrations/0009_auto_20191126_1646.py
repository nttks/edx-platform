# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0008_contractoption_auto_register_reservation_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contractoption',
            name='auto_register_reservation_date',
            field=models.DateField(default=None, null=True, blank=True),
        ),
    ]
