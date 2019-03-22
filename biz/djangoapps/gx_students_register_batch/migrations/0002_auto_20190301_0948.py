# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gx_students_register_batch', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='batchsendmailflag',
            name='contract',
            field=models.OneToOneField(to='ga_contract.Contract'),
        ),
    ]
