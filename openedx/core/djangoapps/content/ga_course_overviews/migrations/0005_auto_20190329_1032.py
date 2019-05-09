# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_course_overviews', '0004_courseoverviewextra_custom_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='courseoverviewextra',
            name='course_category',
            field=models.TextField(default=b'', null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='course_category2',
            field=models.TextField(default=b'', null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='course_category_order',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='course_category_order2',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='course_order',
            field=models.IntegerField(null=True),
        ),
        migrations.AddField(
            model_name='courseoverviewextra',
            name='is_status_managed',
            field=models.BooleanField(default=False),
        ),
    ]
