from django.contrib import admin

from course_modes.models import CourseMode
from .models import PersonalInfoSetting


class PersonalInputSettingAdmin(admin.ModelAdmin):
    def render_change_form(self, request, context, *args, **kwargs):
        context['adminform'].form.fields['course_mode'].queryset = CourseMode.objects.filter(
            mode_slug=CourseMode.NO_ID_PROFESSIONAL_MODE
        )
        return super(PersonalInputSettingAdmin, self).render_change_form(request, context, args, kwargs)

    def display_name(self, obj):
        return obj.advanced_course or obj.course_mode

    def kind(self, obj):
        if obj.advanced_course:
            return obj._meta.get_field_by_name('advanced_course')[0].verbose_name.title()
        else:
            return obj._meta.get_field_by_name('course_mode')[0].verbose_name.title()

    list_display = ['kind', 'display_name']
    list_display_links = ['display_name']


admin.site.register(PersonalInfoSetting, PersonalInputSettingAdmin)
