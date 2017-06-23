# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_contract', '0004_contract_register_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContractOption',
            fields=[
                ('contract', models.OneToOneField(primary_key=True, serialize=False, to='ga_contract.Contract')),
                ('customize_mail', models.BooleanField(default=False)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('modified_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['contract'],
            },
        ),
    ]
