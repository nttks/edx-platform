# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def forwards(apps, schema_editor):
    # forwards data migration to insert default manager permissions only if the permission does not exists.
    ManagerPermission = apps.get_model('ga_manager', 'ManagerPermission')
    db_alias = schema_editor.connection.alias

    objects = ManagerPermission.objects.using(db_alias)
    for name, organization, contract, manager, course_operation, achivement, contract_operation in [
        ('platformer', 1, 1, 1, 0, 0, 0),
        ('aggregator', 1, 1, 1, 0, 0, 0),
        ('director', 0, 0, 1, 1, 1, 1),
        ('manager', 0, 0, 0, 0, 1, 0),
    ]:
        objects.get_or_create(permission_name=name, defaults={
            'can_handle_organization': organization,
            'can_handle_contract': contract,
            'can_handle_manager': manager,
            'can_handle_course_operation': course_operation,
            'can_handle_achievement': achivement,
            'can_handle_contract_operation': contract_operation,
        })


class Migration(migrations.Migration):

    dependencies = [
        ('ga_manager', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards)
    ]
