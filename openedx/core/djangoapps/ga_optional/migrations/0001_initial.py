# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseOptionalConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('key', models.CharField(db_index=True, max_length=100, verbose_name='Feature', choices=[(b'ora2-staff-assessment', 'Staff Assessment for Peer Grading')])),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, verbose_name='Course ID', db_index=True)),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='Changed by')),
            ],
            options={
                'verbose_name': 'Settings for the course optional feature',
                'verbose_name_plural': 'Settings for the course optional feature',
            },
        ),
    ]
