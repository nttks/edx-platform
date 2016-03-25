"""
Views for manager feature
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.ga_manager.views',

    url(r'^$', 'index', name='index'),
    url(r'^modify_ajax', 'modify_ajax', name='modify_ajax'),
    url(r'^list_ajax', 'list_ajax', name='list_ajax'),
)
