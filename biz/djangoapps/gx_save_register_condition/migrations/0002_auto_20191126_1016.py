# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gx_save_register_condition', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='childcondition',
            name='comparison_type',
            field=models.IntegerField(choices=[(1, '\u3068\u7b49\u3057\u3044'), (2, '\u3068\u7b49\u3057\u304f\u306a\u3044'), (3, '\u3092\u542b\u3080'), (4, '\u3092\u542b\u307e\u306a\u3044'), (5, '\u3068\u5148\u982d\u304c\u4e00\u81f4'), (6, '\u3068\u672b\u5c3e\u304c\u4e00\u81f4'), (7, '\u306e\u3044\u305a\u308c\u304b\u3068\u7b49\u3057\u3044'), (8, '\u306e\u3044\u305a\u308c\u3068\u3082\u7b49\u3057\u304f\u306a\u3044')]),
        ),
        migrations.AlterField(
            model_name='parentcondition',
            name='created',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='parentcondition',
            name='modified',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='parentcondition',
            name='setting_type',
            field=models.IntegerField(choices=[(1, '\u7c21\u6613\u8a2d\u5b9a'), (2, '\u4e0a\u7d1a\u8a2d\u5b9a')]),
        ),
    ]
