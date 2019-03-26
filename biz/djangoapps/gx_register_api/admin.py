from django.contrib import admin
from biz.djangoapps.gx_register_api.models import APIContractMail, APIGatewayKey, ChoiceModelForm

class APIContractMailAdmin(admin.ModelAdmin):
    readonly_fields = ['created', 'modified']
    raw_id_fields = ['user']
    form = ChoiceModelForm

class APIGatewayKeyAdmin(admin.ModelAdmin):
    pass

admin.site.register(APIContractMail, APIContractMailAdmin)
admin.site.register(APIGatewayKey)