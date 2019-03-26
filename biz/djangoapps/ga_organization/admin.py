"""
Django admin page for ga_organization models
"""
from django.contrib import admin
from biz.djangoapps.ga_organization.models import OrganizationOption


class OrganizationAdmin(admin.ModelAdmin):
    fields = ['org', 'reservation_mail_date', 'auto_mask_flg', 'modified_by', 'modified']
    list_display = ['org', 'reservation_mail_date', 'auto_mask_flg', 'modified_by', 'modified']
    readonly_fields = ['modified']
    raw_id_fields = ['modified_by']


admin.site.register(OrganizationOption, OrganizationAdmin)
