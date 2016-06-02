
from django.conf import settings
from django.conf.urls import patterns, url

from ga_advanced_course.models import AdvancedCourseTypes


urlpatterns = patterns('ga_advanced_course.views',  # nopep8
    url(r'^choose/{}/$'.format(settings.COURSE_ID_PATTERN), 'choose_advanced_course', name='choose'),
    url(r'^checkout_ticket/(?P<order_id>.+)$', 'checkout_ticket', name='checkout_ticket'),
    url(r'^checkout/$', 'checkout', name='checkout'),
    url(r'^{}/face_to_face$'.format(settings.COURSE_ID_PATTERN),
        'advanced_courses_face_to_face', name='courses_{}'.format(AdvancedCourseTypes.F2F)),
    url(r'^{}/choose_ticket/(?P<advanced_course_id>.+)$'.format(settings.COURSE_ID_PATTERN),
        'choose_ticket', name='choose_ticket'),
    url(r'^{}/purchase_ticket/(?P<ticket_id>.+)$'.format(settings.COURSE_ID_PATTERN),
        'purchase_ticket', name='purchase_ticket'),
)
