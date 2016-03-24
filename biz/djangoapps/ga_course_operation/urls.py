"""
This module for course_operation of biz.
"""
from django.conf import settings
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'biz.djangoapps.ga_course_operation.views',
    url(r'^dashboard/{}$'.format(settings.COURSE_ID_PATTERN), 'dashboard', name='dashboard'),
    url(
        r'^dashboard/{}/register_students$'.format(settings.COURSE_ID_PATTERN),
        'register_students',
        name='register_students'),
    url(r'^dashboard/{}/get_survey'.format(settings.COURSE_ID_PATTERN), 'get_survey', name='get_survey'),
)
