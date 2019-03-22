# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('ga_contract', '0008_contractoption_auto_register_reservation_date'),
        ('ga_organization', '0002_organizationoption'),
    ]


    operations = [
        migrations.CreateModel(
            name='ChildCondition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('parent_condition_name', models.CharField(max_length=255)),
                ('comparison_target', models.CharField(max_length=255, choices=[(b'username', '\u30e6\u30fc\u30b6\u30fc\u540d'), (b'email', '\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9'), (b'login_code', '\u30ed\u30b0\u30a4\u30f3\u30b3\u30fc\u30c9'), (b'code', '\u793e\u54e1\u30b3\u30fc\u30c9'), (b'group_name', '\u7d44\u7e54\u540d'), (b'org1', '\u7d44\u7e541'), (b'org2', '\u7d44\u7e542'), (b'org3', '\u7d44\u7e543'), (b'org4', '\u7d44\u7e544'), (b'org5', '\u7d44\u7e545'), (b'org6', '\u7d44\u7e546'), (b'org7', '\u7d44\u7e547'), (b'org8', '\u7d44\u7e548'), (b'org9', '\u7d44\u7e549'), (b'org10', '\u7d44\u7e5410'), (b'item1', '\u30b0\u30eb\u30fc\u30d71'), (b'item2', '\u30b0\u30eb\u30fc\u30d72'), (b'item3', '\u30b0\u30eb\u30fc\u30d73'), (b'item4', '\u30b0\u30eb\u30fc\u30d74'), (b'item5', '\u30b0\u30eb\u30fc\u30d75'), (b'item6', '\u30b0\u30eb\u30fc\u30d76'), (b'item7', '\u30b0\u30eb\u30fc\u30d77'), (b'item8', '\u30b0\u30eb\u30fc\u30d78'), (b'item9', '\u30b0\u30eb\u30fc\u30d79'), (b'item10', '\u30b0\u30eb\u30fc\u30d710')])),
                ('comparison_type', models.IntegerField(choices=[(1, 'Comparison Equal'), (2, 'Comparison Not Equal'), (3, 'Comparison Contains'), (4, 'Comparison Not Contains'), (5, 'Comparison Starts With'), (6, 'Comparison Ends With'), (7, 'Comparison Equal In'), (8, 'Comparison Not Equal In')])),
                ('comparison_string', models.TextField(null=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
            ],
        ),
        migrations.CreateModel(
            name='ParentCondition',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('parent_condition_name', models.CharField(max_length=255)),
                ('setting_type', models.IntegerField(choices=[(1, 'Simple Setting'), (2, 'Advanced Setting')])),
                ('created', models.DateTimeField(default=datetime.datetime.now)),
                ('modified', models.DateTimeField(default=datetime.datetime.now, null=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
                ('created_by', models.ForeignKey(related_name='creator_parent_condition', to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(related_name='modifier_parent_condition', to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='ReflectConditionTaskHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('task_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('result', models.BooleanField(default=False)),
                ('messages', models.TextField(null=True)),
                ('updated', models.DateTimeField(null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('contract', models.ForeignKey(to='ga_contract.Contract')),
                ('organization', models.ForeignKey(to='ga_organization.Organization')),
                ('requester', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.AddField(
            model_name='childcondition',
            name='parent_condition',
            field=models.ForeignKey(to='gx_save_register_condition.ParentCondition'),
        ),
    ]
