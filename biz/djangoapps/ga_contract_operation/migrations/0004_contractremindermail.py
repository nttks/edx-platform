# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0006_contractoption_send_submission_reminder'),
        ('ga_contract_operation', '0003_contract_oeration_bulkoperation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractReminderMail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mail_type', models.CharField(max_length=255)),
                ('mail_subject', models.CharField(max_length=128)),
                ('mail_body', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('reminder_email_days', models.IntegerField(null=True)),
                ('mail_body2', models.TextField()),
                ('contract', models.ForeignKey(default=None, blank=True, to='ga_contract.Contract', null=True)),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
        migrations.AlterField(
            model_name='contractmail',
            name='mail_type',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='contractremindermail',
            unique_together=set([('contract', 'mail_type')]),
        ),
    ]
