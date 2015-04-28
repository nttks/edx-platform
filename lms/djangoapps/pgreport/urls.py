from django.conf.urls import url, patterns
from django.conf import settings

urlpatterns = patterns('',  # nopep8
    url(r'^get_progress_list/{}/$'.format(settings.COURSE_ID_PATTERN),
        'pgreport.views.ajax_get_progress_list',
        name="get_progress_list"),
    url(r'^get_submission_scores/{}/$'.format(settings.COURSE_ID_PATTERN),
        'pgreport.views.ajax_get_submission_scores',
        name="get_submission_scores"),
    url(r'^get_oa_rubric_scores/{}/$'.format(settings.COURSE_ID_PATTERN),
        'pgreport.views.ajax_get_oa_rubric_scores',
        name="get_oa_rubric_scores"),

)
