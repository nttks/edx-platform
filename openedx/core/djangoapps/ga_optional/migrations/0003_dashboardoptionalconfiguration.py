# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_optional', '0002_add_custom_logo_url_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardOptionalConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('key', models.CharField(max_length=255, verbose_name='Feature', choices=[(b'view-course-button', 'View course button for Mypage')])),
                ('course_key', xmodule_django.models.CourseKeyField(max_length=255, verbose_name='Course ID', db_index=True)),
                ('parts_title_en', models.CharField(max_length=255, verbose_name='Parts Title (EN)', blank=True)),
                ('parts_title_ja', models.CharField(max_length=255, verbose_name='Parts Title (JP)', blank=True)),
                ('href', models.CharField(max_length=255, null=True, verbose_name='href')),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='Changed by')),
            ],
            options={
                'verbose_name': 'Settings for mypage optional feature',
                'verbose_name_plural': 'Settings for mypage optional feature',
            },
        ),
    ]
