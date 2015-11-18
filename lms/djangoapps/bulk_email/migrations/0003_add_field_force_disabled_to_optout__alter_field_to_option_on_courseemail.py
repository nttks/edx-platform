# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bulk_email', '0002_data__load_course_email_template'),
    ]

    operations = [
        migrations.AddField(
            model_name='optout',
            name='force_disabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='courseemail',
            name='to_option',
            field=models.CharField(default=b'myself', max_length=64, choices=[(b'myself', b'Myself'), (b'staff', b'Staff and instructors'), (b'all', b'All'), (b'all_include_optout', b'All including opt-out')]),
        ),
    ]
