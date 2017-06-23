# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('student', '0002_auto_20151208_1034'),
    ]

    operations = [
        migrations.AddField(
            model_name='registration',
            name='masked',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='registration',
            name='modified',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
