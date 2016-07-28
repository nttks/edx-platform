# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('course_overviews', '0005_delete_courseoverviewgeneratedhistory'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseOverviewExtra',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('has_terminated', models.BooleanField(default=False)),
                ('is_f2f_course', models.BooleanField(default=False)),
                ('is_f2f_course_sell', models.BooleanField(default=False)),
                ('course_overview', models.OneToOneField(to='course_overviews.CourseOverview')),
            ],
        ),
    ]
