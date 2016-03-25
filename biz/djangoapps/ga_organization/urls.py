"""
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.ga_organization.views',

    url(r'^$', 'index', name='index'),
    url(r'^show_register$', 'show_register', name='show_register'),
    url(r'^register$', 'register', name='register'),
    url(r'^detail/(?P<selected_id>\d+)$', 'detail', name='detail'),
    url(r'^edit/(?P<selected_id>\d+)$', 'edit', name='edit'),
)
