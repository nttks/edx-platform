from django.contrib import admin
from biz.djangoapps.gx_register_api.models import APIContractMail

class APIContractMailAdmin(admin.ModelAdmin):
    pass

admin.site.register(APIContractMail)