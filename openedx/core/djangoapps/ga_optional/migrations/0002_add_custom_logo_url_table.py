# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_optional', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courseoptionalconfiguration',
            name='key',
            field=models.CharField(db_index=True, max_length=100, verbose_name='Feature', choices=[(b'ora2-staff-assessment', 'Staff Assessment for Peer Grading'), (b'custom-logo-for-settings', 'Custom Logo for Settings')]),
        ),
    ]
