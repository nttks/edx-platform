# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_contract', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlaybackBatchStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('status', models.CharField(db_index=True, max_length=255, choices=[(b'Started', 'Started'), (b'Finished', 'Finished'), (b'Error', 'Error')])),
                ('student_count', models.IntegerField(null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ScoreBatchStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('status', models.CharField(db_index=True, max_length=255, choices=[(b'Started', 'Started'), (b'Finished', 'Finished'), (b'Error', 'Error')])),
                ('student_count', models.IntegerField(null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
