from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.gx_org_group.views',
    url(r'^$', 'group_list', name='group_list'),
    url(r'^detail/(?P<selected_group_id>\d+)$', 'detail', name='detail'),
    url(r'^download_csv$', 'download_csv', name='download_csv'),
    url(r'^upload_csv$', 'upload_csv', name='upload_csv'),
    url(r'^grant_right$', 'grant_right', name='grant_right'),
    url(r'^accessible_user_list$', 'accessible_user_list', name='accessible_user_list'),
    url(r'^accessible_parent_list$', 'accessible_parent_list', name='accessible_parent_list'),
    url(r'^delete_group', 'delete_group', name='delete_group'),
)
