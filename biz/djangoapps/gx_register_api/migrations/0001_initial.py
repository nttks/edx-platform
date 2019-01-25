# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0006_contractoption_send_submission_reminder'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIContractMail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mail_type', models.CharField(max_length=255)),
                ('mail_subject', models.CharField(max_length=128)),
                ('mail_body', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(default=None, blank=True, to='ga_contract.Contract', null=True)),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
        migrations.AlterUniqueTogether(
            name='apicontractmail',
            unique_together=set([('contract', 'mail_type')]),
        ),
    ]
