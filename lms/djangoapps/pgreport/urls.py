from django.conf.urls import url, patterns
from django.conf import settings
from pgreport.views import ProblemReport, SubmissionReport, OpenAssessmentReport


urlpatterns = patterns('',  # nopep8
    url(r'^get_progress_list/{}/$'.format(settings.COURSE_ID_PATTERN),
        'pgreport.views.ajax_get_pgreport',
        {"pgreport": ProblemReport},
        name="get_progress_list"),
    url(r'^get_submission_scores/{}/$'.format(settings.COURSE_ID_PATTERN),
        'pgreport.views.ajax_get_pgreport',
        {"pgreport": SubmissionReport},
        name="get_submission_scores"),
    url(r'^get_oa_rubric_scores/{}/$'.format(settings.COURSE_ID_PATTERN),
        'pgreport.views.ajax_get_pgreport',
        {"pgreport": OpenAssessmentReport},
        name="get_oa_rubric_scores"),
)
