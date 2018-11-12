"""
Django admin page for gx_username_rule models
"""
from django.contrib import admin
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule

class OrgUsernameRuleAdmin(admin.ModelAdmin):
    pass

admin.site.register(OrgUsernameRule)