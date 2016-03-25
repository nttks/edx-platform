"""
URL Conf for achievement(student status) views
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.ga_achievement.views',

    url(r'^$', 'index', name='index'),
    url(r'^download_csv$', 'download_csv', name='download_csv'),
)
