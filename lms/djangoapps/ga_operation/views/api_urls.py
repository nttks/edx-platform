# -*- coding: utf-8 -*-
from django.conf.urls import patterns, url

urlpatterns = patterns(
    '',

    url(r'^confirm_certs_template$',
        'ga_operation.views.api.confirm_certs_template', name="confirm_certs_template"),

    url(r'^upload_certs_template$',
        'ga_operation.views.api.upload_certs_template', name="upload_certs_template"),

    url(r'^create_certs$',
        'ga_operation.views.api.create_certs', name="create_certs"),

    url(r'^create_certs_meeting$',
        'ga_operation.views.api.create_certs_meeting', name="create_certs_meeting"),

    url(r'^publish_certs$',
        'ga_operation.views.api.publish_certs', name="publish_certs"),

    url(r'^move_videos$',
        'ga_operation.views.api.move_videos', name="move_videos"),

    url(r'^mutual_grading_report$',
        'ga_operation.views.api.mutual_grading_report', name="mutual_grading_report"),

    url(r'^discussion_data$',
        'ga_operation.views.api.discussion_data', name="discussion_data"),

    url(r'^discussion_data_download/?$',
        'ga_operation.views.api.discussion_data_download', name="discussion_data_download"),

    url(r'^past_graduates_info/?$',
        'ga_operation.views.api.past_graduates_info', name="past_graduates_info"),

    url(r'^last_login_info/?$',
        'ga_operation.views.api.last_login_info', name="last_login_info"),

    url(r'^aggregate_g1528$',
        'ga_operation.views.api.aggregate_g1528', name="aggregate_g1528"),
)
