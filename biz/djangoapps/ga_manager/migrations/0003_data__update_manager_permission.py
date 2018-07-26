# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards(apps, schema_editor):
    # forwards data migration to insert default manager permissions only if the permission does not exists.
    ManagerPermission = apps.get_model('ga_manager', 'ManagerPermission')
    db_alias = schema_editor.connection.alias

    objects = ManagerPermission.objects.using(db_alias)
    m = objects.filter(permission_name='manager').first()
    m.can_handle_course_operation = False
    m.can_handle_contract_operation = True
    m.save()

class Migration(migrations.Migration):

    dependencies = [
        ('ga_manager', '0001_initial'),
        ('ga_manager', '0002_data__default_manager_permission'),
    ]

    operations = [
        migrations.RunPython(forwards)
    ]
