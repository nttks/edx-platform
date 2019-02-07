"""
Django admin page for gx_member models
"""
from django.contrib import admin
from biz.djangoapps.gx_member.models import Member, MemberRegisterMail


class MemberAdmin(admin.ModelAdmin):
    pass


admin.site.register(Member)
admin.site.register(MemberRegisterMail)
