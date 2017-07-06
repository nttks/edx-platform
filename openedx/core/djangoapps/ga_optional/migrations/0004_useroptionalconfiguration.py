# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_optional', '0003_dashboardoptionalconfiguration'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserOptionalConfiguration',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('change_date', models.DateTimeField(auto_now_add=True, verbose_name='Change date')),
                ('enabled', models.BooleanField(default=False, verbose_name='Enabled')),
                ('key', models.CharField(db_index=True, max_length=100, verbose_name='Feature', choices=[(b'hide-email-settings', 'Hide the e-mail on the Account Settings')])),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, editable=False, to=settings.AUTH_USER_MODEL, null=True, verbose_name='Changed by')),
                ('user', models.ForeignKey(related_name='useroptional', verbose_name='Username', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Settings for the user optional feature',
                'verbose_name_plural': 'Settings for the user optional feature',
            },
        ),
    ]
