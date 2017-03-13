# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards_func(apps, schema_editor):
    apps.get_model('ga_contract', 'Contract').objects.using(schema_editor.connection.alias).all().update(register_type='ERS')


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0003_contractauth_send_mail'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='register_type',
            field=models.CharField(default=b'DRS', max_length=255, choices=[(b'DRS', 'Register by director'), (b'ERS', 'Register by user or director')]),
        ),
        migrations.RunPython(forwards_func),
    ]
