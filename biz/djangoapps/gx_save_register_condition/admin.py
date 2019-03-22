"""
Django admin page for gx_register_condition models
"""
from django.contrib import admin
from biz.djangoapps.gx_save_register_condition.models import ParentCondition, ChildCondition

class ParentConditionAdmin(admin.ModelAdmin):
    """
    Admin for ParentCondition
    """
    raw_id_fields = ('created_by', 'modified_by')


class ChildConditionAdmin(admin.ModelAdmin):
    pass

admin.site.register(ParentCondition, ParentConditionAdmin)
admin.site.register(ChildCondition)

