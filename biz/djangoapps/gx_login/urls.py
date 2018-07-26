from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.gx_login.views',
    url(r'^$', 'index', name='index'),
)
