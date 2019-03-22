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
    url(r'^download_headers_ajax$', 'download_headers_ajax', name='download_headers_ajax'),
    url(r'^update_auto_mask_flg_ajax$', 'update_auto_mask_flg_ajax', name='update_auto_mask_flg_ajax'),

)
