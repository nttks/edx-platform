"""
This module for course_anslist of biz.
"""
from django.conf import settings
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'biz.djangoapps.ga_course_anslist.views',
    # url(r'^hello$', 'hello', name='status_hello'),
    # url(r'^statuslist$', 'statuslist', name='status_list'),
    url(r'^download$', 'download_csv', name='status_download'),
    url(r'^search_api$', 'search_ajax', name='status_search_api'),
)
