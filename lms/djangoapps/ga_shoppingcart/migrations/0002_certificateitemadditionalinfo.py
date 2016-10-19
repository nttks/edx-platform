# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shoppingcart', '0002_auto_20151208_1034'),
        ('ga_shoppingcart', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificateItemAdditionalInfo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('tax', models.DecimalField(default=0.0, max_digits=30, decimal_places=2)),
                ('certificate_item', models.OneToOneField(related_name='additional_info', to='shoppingcart.CertificateItem')),
            ],
        ),
    ]
