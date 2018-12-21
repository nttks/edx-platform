# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract_operation', '0005_additionalinfoupdatetasktarget'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentMemberRegisterTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.CharField(max_length=1024, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('student', models.CharField(max_length=6000)),
                ('history', models.ForeignKey(to='ga_contract_operation.ContractTaskHistory')),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
    ]
