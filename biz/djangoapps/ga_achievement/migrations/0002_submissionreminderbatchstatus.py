# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0004_contract_register_type'),
        ('ga_achievement', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SubmissionReminderBatchStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(db_index=True, max_length=255, choices=[(b'Started', 'Started'), (b'Finished', 'Finished'), (b'Error', 'Error')])),
                ('success_count', models.IntegerField(null=True)),
                ('failure_count', models.IntegerField(null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
