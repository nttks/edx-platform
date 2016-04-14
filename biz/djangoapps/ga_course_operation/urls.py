"""
This module for course_operation of biz.
"""
from django.conf import settings
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'biz.djangoapps.ga_course_operation.views',
    url(r'^register_students$', 'register_students', name='register_students'),
    url(r'^register_students/register_ajax$', 'register_students_ajax', name='register_students_ajax'),
    url(r'^survey$', 'survey', name='survey'),
    url(r'^survey/download$', 'survey_download', name='survey_download'),
)
