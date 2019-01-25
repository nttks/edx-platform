from django.contrib import admin
from biz.djangoapps.gx_register_api.models import APIContractMail, APIGatewayKey

class APIContractMailAdmin(admin.ModelAdmin):
    pass

class APIGatewayKeyAdmin(admin.ModelAdmin):
    pass

admin.site.register(APIContractMail)
admin.site.register(APIGatewayKey)