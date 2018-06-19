# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='SelfPacedCourseClosureReminderBatchStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('status', models.CharField(db_index=True, max_length=255, choices=[(b'Started', 'Started'), (b'Finished', 'Finished'), (b'Error', 'Error')])),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('success_count', models.IntegerField(null=True)),
                ('failure_count', models.IntegerField(null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='SelfPacedCourseClosureReminderMail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mail_type', models.CharField(max_length=255)),
                ('mail_subject', models.CharField(max_length=128)),
                ('mail_body', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('course_id', xmodule_django.models.CourseKeyField(default=None, max_length=255, null=True, db_index=True, blank=True)),
                ('reminder_email_days', models.IntegerField(null=True)),
            ],
            options={
                'ordering': ['id'],
                'abstract': False,
            },
        ),
        migrations.AlterUniqueTogether(
            name='selfpacedcourseclosureremindermail',
            unique_together=set([('course_id', 'mail_type')]),
        ),
    ]
