# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdditionalInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('display_name', models.CharField(max_length=255)),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.CreateModel(
            name='Contract',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('contract_name', models.CharField(max_length=255)),
                ('contract_type', models.CharField(max_length=255, choices=[(b'PF', 'PF Contract'), (b'O', 'Owners Contract'), (b'GS', 'Gacco Service Contract'), (b'OS', 'Owner Service Contract')])),
                ('invitation_code', models.CharField(unique=True, max_length=255)),
                ('start_date', models.DateField()),
                ('end_date', models.DateField()),
                ('created', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('contractor_organization', models.ForeignKey(related_name='org_contractor_contracts', to='ga_organization.Organization')),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
                ('owner_organization', models.ForeignKey(related_name='org_owner_contracts', to='ga_organization.Organization')),
            ],
        ),
        migrations.CreateModel(
            name='ContractDetail',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('contract', models.ForeignKey(related_name='details', to='ga_contract.Contract')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
        migrations.AddField(
            model_name='additionalinfo',
            name='contract',
            field=models.ForeignKey(related_name='additional_info', to='ga_contract.Contract'),
        ),
        migrations.AlterUniqueTogether(
            name='additionalinfo',
            unique_together=set([('contract', 'display_name')]),
        ),
    ]
