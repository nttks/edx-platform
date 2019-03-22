"""
This module for course_operation of biz.
"""
from django.conf import settings
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'biz.djangoapps.ga_course_operation.views',
    url(r'^survey$', 'survey', name='survey'),
    url(r'^survey/download$', 'survey_download', name='survey_download'),
    url(r'^survey/download_cp932$', 'survey_download_cp932', name='survey_download_cp932'),
)
