"""
This module for invitation of biz.
"""
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'biz.djangoapps.ga_invitation.views',
    url(r'^$', 'index', name='index'),
    url(r'^verify$', 'verify', name='verify'),
    url(r'^confirm/(?P<invitation_code>[a-zA-Z0-9]+)$', 'confirm', name='confirm'),
    url(r'^register$', 'register', name='register'),
)
