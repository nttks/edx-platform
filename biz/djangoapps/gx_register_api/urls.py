from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.gx_register_api.views',
    url(r'^v1\.[0-9][0-9]/enrollment/(?P<org_id>\d+)/(?P<contract_id>\d+)/_all', 'post_all', name='post_all'),
    url(r'^v1\.[0-9][0-9]/enrollment/(?P<org_id>\d+)/(?P<contract_id>\d+)/_group', 'post_group', name='post_group'),
    url(r'^v1\.[0-9][0-9]/enrollment/(?P<org_id>\d+)/(?P<contract_id>\d+)/(?P<user_email>.+$)', 'post_user_name', name='post_user_name'),
    url(r'^(?P<start>[\w@]+)', 'post_not_enough', name='post_not_enough'),
)
