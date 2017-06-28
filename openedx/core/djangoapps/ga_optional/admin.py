"""
Django admin page for ga_optional models
"""
from django.contrib import admin

from config_models.admin import KeyedConfigurationModelAdmin

from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration, DashboardOptionalConfiguration


class CourseOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    def get_list_display(self, request):
        return ["id", "enabled", "course_key", "key", "change_date", "changed_by", "edit_link"]


admin.site.register(CourseOptionalConfiguration, CourseOptionalConfigurationAdmin)


class DashboardOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    def get_list_display(self, request):
        return ["id", "enabled", "course_key", "key", "parts_title_en", "parts_title_ja", "href", "change_date", "changed_by", "edit_link"]


admin.site.register(DashboardOptionalConfiguration, DashboardOptionalConfigurationAdmin)
