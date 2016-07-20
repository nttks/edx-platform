# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdditionalInfoSetting',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('display_name', models.CharField(max_length=255)),
                ('value', models.CharField(default=b'', max_length=255)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ContractRegister',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(default=b'Input', max_length=255, choices=[(b'Input', 'Input Invitation'), (b'Register', 'Register Invitation'), (b'Unregister', 'Unregister Invitation')])),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('contract', models.ForeignKey(related_name='contract_register', to='ga_contract.Contract')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ContractRegisterHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('status', models.CharField(max_length=255)),
                ('created', models.DateTimeField()),
                ('modified', models.DateTimeField()),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='contractregister',
            unique_together=set([('contract', 'user')]),
        ),
        migrations.AlterUniqueTogether(
            name='additionalinfosetting',
            unique_together=set([('contract', 'user', 'display_name')]),
        ),
    ]
