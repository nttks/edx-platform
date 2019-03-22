# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0002_organizationoption'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organizationoption',
            name='reservation_mail_date',
            field=models.TimeField(null=True),
        ),
    ]
