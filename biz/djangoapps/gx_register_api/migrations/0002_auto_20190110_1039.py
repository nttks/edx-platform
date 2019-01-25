# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ga_organization', '0001_initial'),
        ('gx_register_api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='APIGatewayKey',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('api_key', models.CharField(max_length=255)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True, null=True)),
                ('org_id', models.ForeignKey(to='ga_organization.Organization')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='apigatewaykey',
            unique_together=set([('api_key', 'org_id')]),
        ),
    ]
