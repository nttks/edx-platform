# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_contract', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractAuth',
            fields=[
                ('contract', models.OneToOneField(primary_key=True, serialize=False, to='ga_contract.Contract')),
                ('url_code', models.CharField(unique=True, max_length=255)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('modified_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['contract'],
            },
        ),
    ]
