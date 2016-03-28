"""
URLconf for contract views
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.ga_contract.views',

    url(r'^$', 'index', name='index'),
    url(r'^show_register$', 'show_register', name='show_register'),
    url(r'^detail/(?P<selected_contract_id>\d+)$', 'detail', name='detail'),
    url(r'^register$', 'register', name='register'),
    url(r'^edit/(?P<selected_contract_id>\d+)$', 'edit', name='edit'),
)
