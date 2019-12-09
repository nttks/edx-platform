# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
from django.conf import settings
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0009_auto_20191126_1646'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_contract_operation', '0006_studentmemberregistertasktarget'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReminderMailTaskHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('task_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
                ('requester', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ReminderMailTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('message', models.CharField(max_length=1024, null=True)),
                ('completed', models.BooleanField(default=False)),
                ('student_email', models.CharField(max_length=255)),
                ('history', models.ForeignKey(to='ga_contract_operation.ReminderMailTaskHistory')),
            ],
        ),
    ]
