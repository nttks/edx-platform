"""
Django admin page for ga_optional models
"""
from django.contrib import admin

from config_models.admin import KeyedConfigurationModelAdmin

from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration


class CourseOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    def get_list_display(self, request):
        return ["id", "enabled", "course_key", "key", "change_date", "changed_by", "edit_link"]


admin.site.register(CourseOptionalConfiguration, CourseOptionalConfigurationAdmin)
