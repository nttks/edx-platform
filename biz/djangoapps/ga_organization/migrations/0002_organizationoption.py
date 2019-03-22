# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_organization', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganizationOption',
            fields=[
                ('org', models.OneToOneField(primary_key=True, serialize=False, to='ga_organization.Organization')),
                ('reservation_mail_date', models.DateTimeField(null=True)),
                ('auto_mask_flg', models.BooleanField(default=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('modified_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['org'],
            },
        ),
    ]
