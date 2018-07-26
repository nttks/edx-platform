# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gx_org_group', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Member',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('code', models.CharField(max_length=255, null=True)),
                ('org1', models.CharField(max_length=255, null=True)),
                ('org2', models.CharField(max_length=255, null=True)),
                ('org3', models.CharField(max_length=255, null=True)),
                ('org4', models.CharField(max_length=255, null=True)),
                ('org5', models.CharField(max_length=255, null=True)),
                ('org6', models.CharField(max_length=255, null=True)),
                ('org7', models.CharField(max_length=255, null=True)),
                ('org8', models.CharField(max_length=255, null=True)),
                ('org9', models.CharField(max_length=255, null=True)),
                ('org10', models.CharField(max_length=255, null=True)),
                ('item1', models.CharField(max_length=255, null=True)),
                ('item2', models.CharField(max_length=255, null=True)),
                ('item3', models.CharField(max_length=255, null=True)),
                ('item4', models.CharField(max_length=255, null=True)),
                ('item5', models.CharField(max_length=255, null=True)),
                ('item6', models.CharField(max_length=255, null=True)),
                ('item7', models.CharField(max_length=255, null=True)),
                ('item8', models.CharField(max_length=255, null=True)),
                ('item9', models.CharField(max_length=255, null=True)),
                ('item10', models.CharField(max_length=255, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('is_delete', models.BooleanField(default=False)),
                ('updated', models.DateTimeField(db_index=True, auto_now=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('created_by', models.ForeignKey(related_name='creator_members', to=settings.AUTH_USER_MODEL)),
                ('creator_org', models.ForeignKey(related_name='creator_org_member', to='ga_organization.Organization')),
                ('group', models.ForeignKey(to='gx_org_group.Group', null=True)),
                ('org', models.ForeignKey(to='ga_organization.Organization')),
                ('updated_by', models.ForeignKey(related_name='updater_members', to=settings.AUTH_USER_MODEL, null=True)),
                ('updated_org', models.ForeignKey(related_name='updater_org_member', to='ga_organization.Organization', null=True)),
                ('user', models.ForeignKey(related_name='member', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='MemberRegisterTaskTarget',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('member', models.CharField(max_length=6000)),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='MemberTaskHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('result', models.BooleanField(default=False)),
                ('messages', models.CharField(max_length=1000000, null=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('organization', models.ForeignKey(to='ga_organization.Organization')),
                ('requester', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='memberregistertasktarget',
            name='history',
            field=models.ForeignKey(to='gx_member.MemberTaskHistory'),
        ),
    ]
