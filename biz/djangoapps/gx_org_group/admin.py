"""
Django admin page for gx_org_group models
"""
from django.contrib import admin
from biz.djangoapps.gx_org_group.models import Group, Right, Parent, Child


class GroupAdmin(admin.ModelAdmin):
    """
    customize: detail fields, and display fields in list
    """
    fields = ['parent_id', 'level_no', 'group_code', 'group_name', 'notes', 'org', 'created_by', ]
    list_display = ['group_name', 'group_code', 'level_no', 'org', 'parent_id', ]


admin.site.register(Group, GroupAdmin)
admin.site.register(Right)
admin.site.register(Parent)
admin.site.register(Child)
