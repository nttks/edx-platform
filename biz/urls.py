"""
URLconf for biz
"""
from django.conf.urls import patterns, include, url


urlpatterns = patterns('',
    #url(r'^$', 'biz.djangoapps.ga_course_selection.views.index', name='index'),

    url(r'^achievement/', include('biz.djangoapps.ga_achievement.urls', namespace='achievement')),
    #url(r'^contract/', include('biz.djangoapps.ga_contract.urls', namespace='contract')),
    #url(r'^course_operation/', include('biz.djangoapps.ga_course_operation.urls', namespace='course_operation')),
    #url(r'^course_selection/', include('biz.djangoapps.ga_course_selection.urls', namespace='course_selection')),
    #url(r'^manager/', include('biz.djangoapps.ga_manager.urls', namespace='manager')),
    #url(r'^organization/', include('biz.djangoapps.ga_organization.urls', namespace='organization')),
    #url(r'^invitation/', include('biz.djangoapps.ga_invitation.urls', namespace='invitation')),
)
