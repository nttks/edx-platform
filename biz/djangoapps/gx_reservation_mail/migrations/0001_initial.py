# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_organization', '0002_organizationoption'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReservationMail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mail_subject', models.CharField(max_length=128)),
                ('mail_body', models.TextField()),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('sent_flag', models.BooleanField(default=False)),
                ('sent_date', models.DateTimeField(null=True)),
                ('org', models.ForeignKey(to='ga_organization.Organization')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
