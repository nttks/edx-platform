# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0007_contractoption_auto_register_students_flg'),
        ('ga_contract_operation', '0006_studentmemberregistertasktarget'),
    ]

    operations = [
        migrations.CreateModel(
            name='BatchSendMailFlag',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, null=True)),
                ('send_mail', models.BooleanField(default=False)),
                ('contract', models.ForeignKey(to='ga_contract.Contract', unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='S3BucketName',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('bucket_name', models.CharField(max_length=255)),
                ('type', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='StudentsRegisterBatchHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('key', models.CharField(max_length=255, null=True)),
                ('message', models.CharField(max_length=255)),
                ('org_id', models.IntegerField(null=True)),
                ('contract_id', models.IntegerField(null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='StudentsRegisterBatchTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('message', models.CharField(max_length=1024, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('student', models.CharField(max_length=1024)),
                ('history', models.ForeignKey(to='ga_contract_operation.ContractTaskHistory')),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
    ]
