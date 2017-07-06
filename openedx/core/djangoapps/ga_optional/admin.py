"""
Django admin page for ga_optional models
"""
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from config_models.admin import KeyedConfigurationModelAdmin

from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration, DashboardOptionalConfiguration, UserOptionalConfiguration


class CourseOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    def get_list_display(self, request):
        return ["id", "enabled", "course_key", "key", "change_date", "changed_by", "edit_link"]


admin.site.register(CourseOptionalConfiguration, CourseOptionalConfigurationAdmin)


class DashboardOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    def get_list_display(self, request):
        return ["id", "enabled", "course_key", "key", "parts_title_en", "parts_title_ja", "href", "change_date", "changed_by", "edit_link"]


admin.site.register(DashboardOptionalConfiguration, DashboardOptionalConfigurationAdmin)


class UserOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    raw_id_fields = ['user', ]

    def get_list_display(self, request):
        return ["id", "enabled", "username", "key", "change_date", "changed_by", "edit_link"]

    def username(self, obj):
        return obj.user.username
    username.short_description = _('Username')
    username.admin_order_field = 'user__username'


admin.site.register(UserOptionalConfiguration, UserOptionalConfigurationAdmin)
