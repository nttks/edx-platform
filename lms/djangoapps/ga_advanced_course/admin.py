"""
Django admin page for ga_course_events
"""
from django.contrib import admin
from .models import AdvancedF2FCourse, AdvancedCourseTicket


class AdvancedF2FCourseAdmin(admin.ModelAdmin):

    list_display = ['course_id', 'display_name']

    fieldsets = (
        (None, {
            'fields': (
                'course_id', 'display_name', 'start_date', 'start_time', 'end_time', 'capacity', 'description',
                'place_name', 'place_link', 'place_address', 'place_access', 'content', 'is_active',
            )
        }),
    )


class AdvancedCourseTicketAdmin(admin.ModelAdmin):

    list_display = ['advanced_course', 'display_name', 'price']


admin.site.register(AdvancedF2FCourse, AdvancedF2FCourseAdmin)
admin.site.register(AdvancedCourseTicket, AdvancedCourseTicketAdmin)
