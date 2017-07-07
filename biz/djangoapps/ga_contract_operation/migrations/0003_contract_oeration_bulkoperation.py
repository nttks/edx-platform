# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract_operation', '0002_auto_20170330_1046'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentUnregisterTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.CharField(max_length=1024, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('inputdata', models.CharField(max_length=1024)),
                ('history', models.ForeignKey(to='ga_contract_operation.ContractTaskHistory')),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
        migrations.AlterModelOptions(
            name='contracttasktarget',
            options={'ordering': ['id']},
        ),
        migrations.AddField(
            model_name='contracttasktarget',
            name='inputdata',
            field=models.CharField(max_length=1024, null=True),
        ),
        migrations.AddField(
            model_name='contracttasktarget',
            name='message',
            field=models.CharField(max_length=1024, null=True),
        ),
        migrations.AlterField(
            model_name='contracttasktarget',
            name='register',
            field=models.ForeignKey(to='ga_invitation.ContractRegister', null=True),
        ),
        migrations.AlterUniqueTogether(
            name='contracttasktarget',
            unique_together=set([]),
        ),
    ]
