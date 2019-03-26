# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gx_sso_config', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ssoconfig',
            name='logout_show',
            field=models.BooleanField(default=0),
        ),
    ]
