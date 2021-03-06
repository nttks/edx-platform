# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SsoConfig',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('idp_slug', models.SlugField(max_length=30)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified', models.DateTimeField(db_index=True, auto_now=True, null=True)),
                ('org', models.ForeignKey(to='ga_organization.Organization')),
            ],
        ),
    ]
