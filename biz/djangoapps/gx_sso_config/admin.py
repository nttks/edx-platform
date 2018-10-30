from django.contrib import admin
from biz.djangoapps.gx_sso_config.models import SsoConfig

class SsoConfigAdmin(admin.ModelAdmin):
    pass

admin.site.register(SsoConfig)