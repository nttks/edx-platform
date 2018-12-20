# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract_operation', '0004_contractremindermail'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdditionalInfoUpdateTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.CharField(max_length=1024, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('inputline', models.TextField()),
                ('history', models.ForeignKey(to='ga_contract_operation.ContractTaskHistory')),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
    ]
