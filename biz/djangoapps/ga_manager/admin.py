"""
Admin for ga_manager.
"""
from django.contrib import admin

from .models import Manager


class ManagerAdmin(admin.ModelAdmin):
    """
    Admin for Manager
    """
    list_display = ['id', 'orgname', 'username', 'permissions']
    raw_id_fields = ['user']

    def orgname(self, obj):
        """
        org name
        """
        return obj.org.org_name
    orgname.short_description = 'Org name'

    def username(self, obj):
        """
        user name
        """
        return obj.user.username
    username.short_description = 'User name'

    def permissions(self, obj):
        """
        permissions
        """
        return ','.join([x.permission_name for x in obj.manager_permissions.all()])
    permissions.short_description = 'Permissions'


admin.site.register(Manager, ManagerAdmin)
