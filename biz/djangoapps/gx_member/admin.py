"""
Django admin page for gx_member models
"""
from django.contrib import admin
from biz.djangoapps.gx_member.models import Member


class MemberAdmin(admin.ModelAdmin):
    pass

admin.site.register(Member)
