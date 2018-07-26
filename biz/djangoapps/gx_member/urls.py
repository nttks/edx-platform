"""
URLconf for member views
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.gx_member.views',

    url(r'^$', 'index', name='index'),
    url(r'^register_ajax$', 'register_ajax', name='register_ajax'),
    url(r'^register_csv_ajax$', 'register_csv_ajax', name='register_csv_ajax'),
    url(r'^task_history_ajax$', 'task_history_ajax', name='task_history_ajax'),
    url(r'^download_ajax$', 'download_ajax', name='download_ajax'),

)
