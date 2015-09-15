"""
Django admin page for MaintenanceMessage
"""
from django.contrib import admin
from ga_maintenance_cms.models import MaintenanceMessage


class MaintenanceMessageAdmin(admin.ModelAdmin):
    list_display = ['message', 'display_order', 'display_flg']

admin.site.register(MaintenanceMessage, MaintenanceMessageAdmin)
