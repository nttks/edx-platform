"""
Django admin page for ga_optional models
"""
from django import forms
from django.contrib import admin
from django.utils.translation import ugettext_lazy as _

from config_models.admin import KeyedConfigurationModelAdmin
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore

from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration, DashboardOptionalConfiguration, UserOptionalConfiguration, SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_KEY


class CourseOptionalConfigurationForm(forms.ModelForm):

    class Meta:
        model = CourseOptionalConfiguration
        fields = '__all__'

    def clean_course_key(self):
        course_key = self.cleaned_data['course_key']
        try:
            course_key = CourseKey.from_string(course_key)
            course = modulestore().get_course(course_key)
            if course_key is None or not course:
                raise forms.ValidationError(_("This course does not exist. Please change course id."))
        except InvalidKeyError:
            raise forms.ValidationError(_("This course is invalid. Please change course id."))

        return self.cleaned_data['course_key']

    def clean(self):
        cleaned_data = super(CourseOptionalConfigurationForm, self).clean()
        key = cleaned_data['key'] if 'key' in cleaned_data else None
        course_key = cleaned_data['course_key'] if 'course_key' in cleaned_data else None

        if not self.has_error('course_key'):
            course_key = CourseKey.from_string(course_key)
            course = modulestore().get_course(course_key)
            if key == SELF_PACED_COURSE_CLOSURE_REMINDER_EMAIL_KEY and course_key is not None:
                if not course.self_paced:
                    raise forms.ValidationError(_("This course is not self-paced. Please change course id."))

        return cleaned_data


class CourseOptionalConfigurationAdmin(KeyedConfigurationModelAdmin):

    form = CourseOptionalConfigurationForm

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
