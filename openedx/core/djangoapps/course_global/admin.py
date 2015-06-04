"""
Django admin page for course global models
"""
from django.contrib import admin
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting


class CourseGlobalSettingAdmin(admin.ModelAdmin):
    pass

admin.site.register(CourseGlobalSetting, CourseGlobalSettingAdmin)
