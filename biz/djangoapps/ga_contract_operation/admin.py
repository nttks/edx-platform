"""
Django admin page for ga_contract_operation models
"""
from django.contrib import admin

from biz.djangoapps.ga_contract_operation.models import ContractMail, ContractReminderMail


class ContractMailAdmin(admin.ModelAdmin):
    pass


class ContractReminderMailAdmin(admin.ModelAdmin):
    pass


admin.site.register(ContractMail, ContractMailAdmin)
admin.site.register(ContractReminderMail, ContractReminderMailAdmin)
