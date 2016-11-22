# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('course_modes', '0005_auto_20161118_1417'),
        ('shoppingcart', '0003_auto_20161118_1417'),
        ('ga_advanced_course', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_shoppingcart', '0002_certificateitemadditionalinfo'),
    ]

    operations = [
        migrations.CreateModel(
            name='PersonalInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('full_name', models.CharField(max_length=255, null=True, verbose_name='\u6c0f\u540d')),
                ('kana', models.CharField(max_length=255, null=True, verbose_name='\u30d5\u30ea\u30ac\u30ca', blank=True)),
                ('postal_code', models.CharField(max_length=7, null=True, verbose_name='\u90f5\u4fbf\u756a\u53f7')),
                ('address_line_1', models.CharField(max_length=255, null=True, verbose_name='\u4f4f\u62401')),
                ('address_line_2', models.CharField(max_length=255, null=True, verbose_name='\u4f4f\u62402', blank=True)),
                ('phone_number', models.CharField(max_length=32, null=True, verbose_name='\u96fb\u8a71\u756a\u53f7')),
                ('gaccatz_check', models.CharField(max_length=1024, null=True, verbose_name='\u304a\u4f7f\u3044\u306e\u74b0\u5883\u30b9\u30da\u30c3\u30af\u306b\u3064\u3044\u3066\u3054\u8a18\u5165\u304f\u3060\u3055\u3044<br>\uff08ex: MacBook Air, 1.6GHz \u30a4\u30f3\u30c6\u30eb i5, 8GB RAM, FTTH (\u30d5\u30ec\u30c3\u30c4\u5149))')),
                ('free_entry_field_1', models.CharField(max_length=1024, null=True, verbose_name='Free Entry Field 1')),
                ('free_entry_field_2', models.CharField(max_length=1024, null=True, verbose_name='Free Entry Field 2')),
                ('free_entry_field_3', models.CharField(max_length=1024, null=True, verbose_name='Free Entry Field 3')),
                ('free_entry_field_4', models.CharField(max_length=1024, null=True, verbose_name='Free Entry Field 4')),
                ('free_entry_field_5', models.CharField(max_length=1024, null=True, verbose_name='Free Entry Field 5')),
            ],
        ),
        migrations.CreateModel(
            name='PersonalInfoSetting',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('full_name', models.BooleanField(default=True, verbose_name='\u6c0f\u540d')),
                ('kana', models.BooleanField(default=True, verbose_name='\u30d5\u30ea\u30ac\u30ca')),
                ('postal_code', models.BooleanField(default=True, verbose_name='\u90f5\u4fbf\u756a\u53f7')),
                ('address_line_1', models.BooleanField(default=True, verbose_name='\u4f4f\u62401')),
                ('address_line_2', models.BooleanField(default=True, verbose_name='\u4f4f\u62402')),
                ('phone_number', models.BooleanField(default=True, verbose_name='\u96fb\u8a71\u756a\u53f7')),
                ('gaccatz_check', models.BooleanField(default=True, verbose_name='Gaccatz Check')),
                ('free_entry_field_1_title', models.TextField(verbose_name='Free Entry Field 1 Title', blank=True)),
                ('free_entry_field_2_title', models.TextField(verbose_name='Free Entry Field 2 Title', blank=True)),
                ('free_entry_field_3_title', models.TextField(verbose_name='Free Entry Field 3 Title', blank=True)),
                ('free_entry_field_4_title', models.TextField(verbose_name='Free Entry Field 4 Title', blank=True)),
                ('free_entry_field_5_title', models.TextField(verbose_name='Free Entry Field 5 Title', blank=True)),
                ('advanced_course', models.OneToOneField(null=True, blank=True, to='ga_advanced_course.AdvancedCourse', verbose_name='Event ID')),
                ('course_mode', models.OneToOneField(null=True, blank=True, to='course_modes.CourseMode', verbose_name='Professional Course ID')),
            ],
        ),
        migrations.AddField(
            model_name='personalinfo',
            name='choice',
            field=models.ForeignKey(to='ga_shoppingcart.PersonalInfoSetting'),
        ),
        migrations.AddField(
            model_name='personalinfo',
            name='order',
            field=models.ForeignKey(to='shoppingcart.Order'),
        ),
        migrations.AddField(
            model_name='personalinfo',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='personalinfo',
            unique_together=set([('user', 'order')]),
        ),
    ]
