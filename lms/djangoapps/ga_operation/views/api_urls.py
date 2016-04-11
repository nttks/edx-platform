# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns(
    '',

    url(r'^create_certs$',
        'ga_operation.views.api.create_certs', name="create_certs"),

    url(r'^create_certs_meeting$',
        'ga_operation.views.api.create_certs_meeting', name="create_certs_meeting"),

    url(r'^publish_certs$',
        'ga_operation.views.api.publish_certs', name="publish_certs"),

    url(r'^move_videos$',
        'ga_operation.views.api.move_videos', name="move_videos"),
)
