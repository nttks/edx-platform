"""
URLconf for member views
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.gx_save_register_condition.views',

    url(r'^$', 'index', name='index'),
    url(r'^search_target_ajax$', 'search_target_ajax', name='search_target_ajax'),
    url(r'^add_condition_ajax$', 'add_condition_ajax', name='add_condition_ajax'),
    url(r'^delete_condition_ajax$', 'delete_condition_ajax', name='delete_condition_ajax'),
    url(r'^copy_condition_ajax$', 'copy_condition_ajax', name='copy_condition_ajax'),
    url(r'^reflect_condition_ajax$', 'reflect_condition_ajax', name='reflect_condition_ajax'),
    url(r'^task_history_ajax$', 'task_history_ajax', name='task_history_ajax'),
    url(r'^update_auto_register_students_flg$', 'update_auto_register_students_flg',
        name='update_auto_register_students_flg'),
    url(r'^reservation_date_ajax$', 'reservation_date_ajax', name='reservation_date_ajax'),
    url(r'^cancel_reservation_date_ajax$', 'cancel_reservation_date_ajax', name='cancel_reservation_date_ajax'),
    url(r'^detail/(?P<condition_id>\d+)$', 'detail', name='detail'),
    url(r'^detail/search_target_ajax$', 'detail_search_target_ajax', name='detail_search_target_ajax'),
    url(r'^detail/simple/save_condition_ajax$', 'detail_simple_save_condition_ajax',name='detail_simple_save_condition_ajax'),
    url(r'^detail/advanced/save_condition_ajax$', 'detail_advanced_save_condition_ajax', name='detail_advanced_save_condition_ajax'),
)
