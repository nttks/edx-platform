# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AdvancedCourse',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, verbose_name='course_id', db_index=True)),
                ('display_name', models.CharField(max_length=255, verbose_name='Display Name')),
                ('start_date', models.DateField(verbose_name='Start Date')),
                ('start_time', models.TimeField(verbose_name='Start Time')),
                ('end_time', models.TimeField(verbose_name='End Time')),
                ('capacity', models.IntegerField(default=0, verbose_name='Capacity')),
                ('description', models.CharField(max_length=1000, verbose_name='Description')),
                ('content', models.TextField(verbose_name='Other information', blank=True)),
                ('is_active', models.BooleanField(default=True, verbose_name='Enabled')),
            ],
        ),
        migrations.CreateModel(
            name='AdvancedCourseTicket',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('display_name', models.CharField(max_length=255, verbose_name='Display Name')),
                ('price', models.IntegerField(default=0, verbose_name='Price of ticket')),
                ('sell_by_date', models.DateTimeField(verbose_name='Sell-by date')),
                ('description', models.CharField(max_length=255, verbose_name='Description')),
                ('display_order', models.IntegerField(default=99, verbose_name='Display Order')),
            ],
            options={
                'verbose_name': 'Ticket',
                'verbose_name_plural': 'Ticket',
            },
        ),
        migrations.CreateModel(
            name='AdvancedF2FCourse',
            fields=[
                ('advancedcourse_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='ga_advanced_course.AdvancedCourse')),
                ('place_name', models.CharField(max_length=100, verbose_name='Meeting Place', blank=True)),
                ('place_link', models.URLField(verbose_name='Meeting Place Url', blank=True)),
                ('place_address', models.CharField(max_length=255, verbose_name='Address', blank=True)),
                ('place_access', models.CharField(max_length=1000, verbose_name='Access', blank=True)),
            ],
            options={
                'verbose_name': 'Face 2 Face Classroom',
                'verbose_name_plural': 'Face 2 Face Classroom',
            },
            bases=('ga_advanced_course.advancedcourse',),
        ),
        migrations.AddField(
            model_name='advancedcourseticket',
            name='advanced_course',
            field=models.ForeignKey(verbose_name='Face 2 Face Classroom', to='ga_advanced_course.AdvancedCourse'),
        ),
    ]
