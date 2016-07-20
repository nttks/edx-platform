# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        ('shoppingcart', '0002_auto_20151208_1034'),
        ('ga_advanced_course', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdvancedCourseItem',
            fields=[
                ('orderitem_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='shoppingcart.OrderItem')),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=128, db_index=True)),
                ('tax', models.DecimalField(default=0.0, max_digits=30, decimal_places=2)),
                ('advanced_course_ticket', models.ForeignKey(to='ga_advanced_course.AdvancedCourseTicket')),
            ],
            options={
                'abstract': False,
            },
            bases=('shoppingcart.orderitem',),
        ),
    ]
