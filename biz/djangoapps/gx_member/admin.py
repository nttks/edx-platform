"""
Django admin page for gx_member models
"""
from django.contrib import admin
from biz.djangoapps.gx_member.models import Member, MemberTaskHistory, MemberRegisterMail


class MemberAdmin(admin.ModelAdmin):
    raw_id_fields = ('user', 'updated_by', 'created_by')
    pass


admin.site.register(Member)
admin.site.register(MemberTaskHistory)
admin.site.register(MemberRegisterMail)