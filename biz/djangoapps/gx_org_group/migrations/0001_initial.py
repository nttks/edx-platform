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
            name='Child',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('list', models.CharField(max_length=65535, null=True, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('parent_id', models.IntegerField()),
                ('level_no', models.IntegerField()),
                ('group_code', models.CharField(max_length=20)),
                ('group_name', models.CharField(max_length=255)),
                ('notes', models.CharField(max_length=255, null=True, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(db_index=True, auto_now=True, null=True)),
                ('created_by', models.ForeignKey(related_name='creator_groups', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(related_name='modifier_groups', default=None, to=settings.AUTH_USER_MODEL, null=True)),
                ('org', models.ForeignKey(to='ga_organization.Organization')),
            ],
        ),
        migrations.CreateModel(
            name='Parent',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('path', models.CharField(max_length=65535, null=True, blank=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('group', models.ForeignKey(related_name='parent', to='gx_org_group.Group')),
                ('org', models.ForeignKey(related_name='parents', to='ga_organization.Organization')),
            ],
        ),
        migrations.CreateModel(
            name='Right',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('created_by', models.ForeignKey(related_name='creator_rights', to=settings.AUTH_USER_MODEL)),
                ('creator_org', models.ForeignKey(related_name='creator_org_rights', to='ga_organization.Organization')),
                ('group', models.ForeignKey(to='gx_org_group.Group')),
                ('org', models.ForeignKey(related_name='rights', to='ga_organization.Organization')),
                ('user', models.ForeignKey(related_name='right', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='child',
            name='group',
            field=models.ForeignKey(related_name='child', to='gx_org_group.Group'),
        ),
        migrations.AddField(
            model_name='child',
            name='org',
            field=models.ForeignKey(related_name='children', to='ga_organization.Organization'),
        ),
    ]
