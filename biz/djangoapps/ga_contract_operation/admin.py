"""
Django admin page for ga_contract_operation models
"""
from django.contrib import admin

from biz.djangoapps.ga_contract_operation.models import ContractMail


class ContractMailAdmin(admin.ModelAdmin):
    pass


admin.site.register(ContractMail, ContractMailAdmin)
