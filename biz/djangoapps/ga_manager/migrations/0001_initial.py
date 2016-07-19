# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Manager',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='ManagerPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('permission_name', models.CharField(max_length=255, choices=[(b'platformer', 'platformer'), (b'aggregator', 'aggregator'), (b'director', 'director'), (b'manager', 'manager')])),
                ('can_handle_organization', models.BooleanField()),
                ('can_handle_contract', models.BooleanField()),
                ('can_handle_manager', models.BooleanField()),
                ('can_handle_course_operation', models.BooleanField()),
                ('can_handle_achievement', models.BooleanField()),
                ('can_handle_contract_operation', models.BooleanField()),
            ],
        ),
        migrations.AddField(
            model_name='manager',
            name='manager_permissions',
            field=models.ManyToManyField(related_name='managers', to='ga_manager.ManagerPermission'),
        ),
        migrations.AddField(
            model_name='manager',
            name='org',
            field=models.ForeignKey(related_name='managers', to='ga_organization.Organization'),
        ),
        migrations.AddField(
            model_name='manager',
            name='user',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL),
        ),
    ]
