"""
Django admin page for ratelimit-backend
"""
from django.contrib import admin
from openedx.core.djangoapps.ga_ratelimitbackend.models import TrustedClient


class TrustedClientAdmin(admin.ModelAdmin):
    pass

admin.site.register(TrustedClient, TrustedClientAdmin)
