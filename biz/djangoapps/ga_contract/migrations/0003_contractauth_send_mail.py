# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0002_contractauth'),
    ]

    operations = [
        migrations.AddField(
            model_name='contractauth',
            name='send_mail',
            field=models.BooleanField(default=False),
        ),
    ]
