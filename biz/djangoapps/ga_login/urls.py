"""
URLconf for login views
"""
from django.conf.urls import patterns, url

from biz.djangoapps.ga_contract.models import URL_CODE_PATTERN


urlpatterns = patterns(
    'biz.djangoapps.ga_login.views',

    url(r'^{url_code}$'.format(url_code=URL_CODE_PATTERN), 'index', name='index'),
    url(r'^submit$', 'submit', name='submit'),
)
