"""
URLconf for ga_app
"""
from django.conf import settings
from django.conf.urls import patterns, include, url


urlpatterns = patterns('',
    url(r'^ga_diagnosis/{}?/'.format(settings.COURSE_ID_PATTERN),
        include('ga_app.djangoapps.ga_diagnosis.urls', namespace='diagnosis')),
)
