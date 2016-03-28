"""
URLconf for course selection views
"""
from django.conf.urls import patterns, url


urlpatterns = patterns(
    'biz.djangoapps.ga_course_selection.views',

    url(r'^change$', 'change', name='change'),
)
