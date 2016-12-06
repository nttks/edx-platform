# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_advanced_course', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='advancedf2fcourse',
            options={'verbose_name': 'Face-to-Face Course', 'verbose_name_plural': 'Face-to-Face Course'},
        ),
        migrations.AlterField(
            model_name='advancedcourse',
            name='content',
            field=models.TextField(verbose_name='Other Information', blank=True),
        ),
        migrations.AlterField(
            model_name='advancedcourseticket',
            name='advanced_course',
            field=models.ForeignKey(verbose_name='Face-to-Face Course', to='ga_advanced_course.AdvancedCourse'),
        ),
        migrations.AlterField(
            model_name='advancedcourseticket',
            name='price',
            field=models.IntegerField(default=0, verbose_name='Price of Ticket'),
        ),
        migrations.AlterField(
            model_name='advancedcourseticket',
            name='sell_by_date',
            field=models.DateTimeField(verbose_name='Sell-by Date'),
        ),
    ]
