# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0004_contract_register_type'),
        ('ga_contract_operation', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractMail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mail_type', models.CharField(max_length=255, choices=[(b'RNU', 'For New User'), (b'REU', 'For Existing User'), (b'RNUWLC', 'For New User with Login Code'), (b'REUWLC', 'For Existing User with Login Code')])),
                ('mail_subject', models.CharField(max_length=128)),
                ('mail_body', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(default=None, blank=True, to='ga_contract.Contract', null=True)),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AlterModelOptions(
            name='studentregistertasktarget',
            options={'ordering': ['id']},
        ),
        migrations.AlterUniqueTogether(
            name='contractmail',
            unique_together=set([('contract', 'mail_type')]),
        ),
    ]
