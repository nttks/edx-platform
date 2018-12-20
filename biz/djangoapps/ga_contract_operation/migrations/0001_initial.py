# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_invitation', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractTaskHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
                ('requester', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ContractTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('history', models.ForeignKey(to='ga_contract_operation.ContractTaskHistory')),
                ('register', models.ForeignKey(to='ga_invitation.ContractRegister')),
            ],
        ),
        migrations.CreateModel(
            name='StudentRegisterTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('student', models.CharField(max_length=1024)),
                ('message', models.CharField(max_length=1024, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('history', models.ForeignKey(to='ga_contract_operation.ContractTaskHistory')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='contracttasktarget',
            unique_together=set([('history', 'register')]),
        ),
    ]
