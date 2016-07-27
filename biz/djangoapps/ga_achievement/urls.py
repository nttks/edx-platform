"""
URL Conf for achievement(student status) views
"""
from django.conf.urls import patterns, url

urlpatterns = patterns(
    'biz.djangoapps.ga_achievement.views',

    url(r'^score$', 'score', name='score'),
    url(r'^score_download_csv$', 'score_download_csv', name='score_download_csv'),
    url(r'^playback$', 'playback', name='playback'),
    url(r'^playback_download_csv$', 'playback_download_csv', name='playback_download_csv'),
)
