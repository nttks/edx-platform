# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_shoppingcart', '0003_auto_20161205_1514'),
    ]

    operations = [
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_1_textbox',
            field=models.BooleanField(default=False, verbose_name='Free Entry Field 1 TextBox'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_1_validation',
            field=models.IntegerField(default=0, verbose_name='Free Entry Field 1 Validation'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_2_textbox',
            field=models.BooleanField(default=False, verbose_name='Free Entry Field 2 TextBox'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_2_validation',
            field=models.IntegerField(default=0, verbose_name='Free Entry Field 2 Validation'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_3_textbox',
            field=models.BooleanField(default=False, verbose_name='Free Entry Field 3 TextBox'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_3_validation',
            field=models.IntegerField(default=0, verbose_name='Free Entry Field 3 Validation'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_4_textbox',
            field=models.BooleanField(default=False, verbose_name='Free Entry Field 4 TextBox'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_4_validation',
            field=models.IntegerField(default=0, verbose_name='Free Entry Field 4 Validation'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_5_textbox',
            field=models.BooleanField(default=False, verbose_name='Free Entry Field 5 TextBox'),
        ),
        migrations.AddField(
            model_name='personalinfosetting',
            name='free_entry_field_5_validation',
            field=models.IntegerField(default=0, verbose_name='Free Entry Field 5 Validation'),
        ),
    ]
