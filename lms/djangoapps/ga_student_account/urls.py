# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'ga_student_account.views',  # nopep8
    url('^get_org_username_rules$', 'get_org_username_rules', name='get_org_username_rules'),
    url('^check_redirect_saml_login$', 'check_redirect_saml_login', name='check_redirect_saml_login'),
)