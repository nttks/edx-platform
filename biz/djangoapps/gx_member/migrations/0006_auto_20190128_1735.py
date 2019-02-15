# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0001_initial'),
        ('gx_member', '0005_auto_20181211_1429'),
    ]

    operations = [
        migrations.CreateModel(
            name='MemberRegisterMail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mail_to', models.CharField(max_length=255)),
                ('mail_subject', models.CharField(max_length=128)),
                ('mail_body', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, null=True)),
                ('org_id', models.ForeignKey(to='ga_organization.Organization')),
            ],
            options={
                'ordering': ['org_id'],
            },
        ),
        migrations.AlterField(
            model_name='member',
            name='created',
            field=models.DateTimeField(auto_now_add=True, db_index=True),
        ),
    ]
