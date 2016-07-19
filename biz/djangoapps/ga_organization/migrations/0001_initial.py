# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('org_name', models.CharField(max_length=255)),
                ('org_code', models.CharField(max_length=64)),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('creator_org', models.ForeignKey(related_name='creator_orgs', to='ga_organization.Organization')),
            ],
        ),
    ]
