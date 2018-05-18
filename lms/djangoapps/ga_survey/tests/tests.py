"""
Test the lms/ga_survey views.
"""

import json
import logging
import urllib

from django.http import HttpResponseNotAllowed, Http404
from django.test import TestCase
from django.test.client import RequestFactory

from ga_survey.models import SurveySubmission
from ga_survey.tests.factories import SurveySubmissionFactory
from ga_survey.views import survey_init, survey_ajax
from opaque_keys.edx.locator import CourseLocator
from student.tests.factories import UserFactory


log = logging.getLogger(__name__)


class SuveyTests(TestCase):
    """
    Tests for survey functionality
    """
    request_factory = RequestFactory()

    def setUp(self):
        self.user = UserFactory.create()
        self.course_id = CourseLocator.from_string('edX/test/course1')
        self.unit_id = '22222222222222222222222222222222'
        self.survey_name = 'survey #2'
        self.survey_answer = u'{"Q1": "1", "Q2": ["2", "3"], "Q3": "\U00000053\U00000054\U00000041\U00000052' \
                             u'\U00000054\U00002600\U00000074\U00000065\U00000073\U00000074\U0001F600\U00000074' \
                             u'\U00000065\U00000073\U00000074\U0002000B\U00000074\U00000065\U00000073\U00000074' \
                             u'\U0001F1EF\U0001F1F5\U00000074\U00000065\U00000073\U00000074\U0001F3F4\U000E0067' \
                             u'\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F\U00000074\U00000065\U00000073' \
                             u'\U00000074\U0001F468\U0000200D\U0001F469\U0000200D\U0001F467\U0000200D\U0001F466' \
                             u'\U00000045\U0000004E\U00000044"}'
        self.survey_answer = self.survey_answer.encode('utf-8')
        self.survey_answer_expected_dict = json.loads(self.survey_answer)

    def _post_as_ajax(self, path, data):
        return self.request_factory.post(path, urllib.urlencode(data), content_type='application/json')

    def test_survey_init_get_method_not_allowed(self):
        """Ensures that get request to /survey_init/ is not allowed"""
        req = self.request_factory.get('/survey_init/')
        resp = survey_init(req)
        self.assertIsInstance(resp, HttpResponseNotAllowed)

    def test_survey_init_with_empty_course_id(self):
        """Ensures that request with empty course_id raises Http404"""
        data = {
            'unit_id': self.unit_id,
        }
        req = self._post_as_ajax('/survey_init/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_init, req)

    def test_survey_init_with_empty_unit_id(self):
        """Ensures that request with empty unit_id raises Http404"""
        data = {
            'course_id': self.course_id,
        }
        req = self._post_as_ajax('/survey_init/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_init, req)

    def test_survey_init_success(self):
        """Ensures that /survey_init/ succeeds"""
        data = {
            'course_id': self.course_id,
            'unit_id': self.unit_id,
        }
        req = self._post_as_ajax('/survey_init/', data)
        req.user = self.user
        resp = survey_init(req)
        self.assertEquals(resp.status_code, 200)
        obj = json.loads(resp.content)
        self.assertEquals(obj, {
            'success': True,
        })

    def test_survey_init_fail_when_already_submitted(self):
        """Ensures that /survey_init/ fails when survey_submission already exists"""
        submission = SurveySubmissionFactory.create()

        data = {
            'course_id': submission.course_id,
            'unit_id': submission.unit_id,
        }
        req = self._post_as_ajax('/survey_init/', data)
        req.user = submission.user
        resp = survey_init(req)
        self.assertEquals(resp.status_code, 200)
        obj = json.loads(resp.content)
        self.assertEquals(obj, {
            'success': False,
            'survey_answer': submission.get_survey_answer(),
        })

    def test_survey_ajax_get_method_not_allowed(self):
        """Ensures that get request to /survey_ajax/ is not allowed"""
        req = self.request_factory.get('/survey_ajax/')
        resp = survey_ajax(req)
        self.assertIsInstance(resp, HttpResponseNotAllowed)

    def test_survey_ajax_with_empty_course_id(self):
        """Ensures that request with empty course_id raises Http404"""
        data = {
            'unit_id': self.unit_id,
            'survey_name': self.survey_name,
            'survey_answer': self.survey_answer,
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_ajax, req)

    def test_survey_ajax_with_empty_unit_id(self):
        """Ensures that request with empty unit_id raises Http404"""
        data = {
            'course_id': self.course_id,
            'survey_name': self.survey_name,
            'survey_answer': self.survey_answer,
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_ajax, req)

    def test_survey_ajax_with_empty_survey_name(self):
        """Ensures that request with empty survey_name raises Http404"""
        data = {
            'course_id': self.course_id,
            'unit_id': self.unit_id,
            'survey_answer': self.survey_answer,
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_ajax, req)

    def test_survey_ajax_with_empty_survey_answer(self):
        """Ensures that request with empty survey_answer raises Http404"""
        data = {
            'course_id': self.course_id,
            'unit_id': self.unit_id,
            'survey_name': self.survey_name,
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_ajax, req)

    def test_survey_ajax_success(self):
        """Ensures that /survey_ajax/ succeeds"""
        data = {
            'course_id': self.course_id,
            'unit_id': self.unit_id,
            'survey_name': self.survey_name,
            'survey_answer': self.survey_answer,
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = self.user
        resp = survey_ajax(req)
        self.assertEquals(resp.status_code, 200)
        obj = json.loads(resp.content)
        self.assertEquals(obj, {
            'success': True,
        })
        # assert that SurveySubmission record is created
        submissions = SurveySubmission.objects.filter(
            course_id=self.course_id,
            unit_id=self.unit_id,
            user=self.user
        )
        self.assertEquals(len(submissions), 1)
        self.assertEquals(submissions[0].survey_name, self.survey_name)

        ans_dict = submissions[0].get_survey_answer()
        keyset = ans_dict.keys()
        keys = sorted(keyset)
        self.assertEquals(len(keys), 3)
        self.assertEquals(len(ans_dict), 3)
        self.assertEquals(len(self.survey_answer_expected_dict), 3)
        for key in keys:
            value = ans_dict.get(key, 'N/A')
            value_expected = self.survey_answer_expected_dict.get(key, 'N/A')
            self.assertEquals(value, value_expected)

    def test_survey_ajax_fail_when_already_submitted(self):
        """Ensures that /survey_ajax/ fails when survey_submission already exists"""
        submission = SurveySubmissionFactory.create()

        data = {
            'course_id': submission.course_id,
            'unit_id': submission.unit_id,
            'survey_name': self.survey_name,
            'survey_answer': self.survey_answer,
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = submission.user
        resp = survey_ajax(req)
        self.assertEquals(resp.status_code, 200)
        obj = json.loads(resp.content)
        self.assertEquals(obj, {
            'success': False,
            'survey_answer': submission.get_survey_answer(),
        })

    def test_survey_ajax_with_unloadable_survey_answer(self):
        """Ensures that request with unloadable survey_answer raises Http404"""
        data = {
            'course_id': self.course_id,
            'unit_id': self.unit_id,
            'survey_name': self.survey_name,
            'survey_answer': 'This cannot be loaded by json.loads',
        }
        req = self._post_as_ajax('/survey_ajax/', data)
        req.user = self.user
        self.assertRaises(Http404, survey_ajax, req)

    def test_survey_models_survey_submission(self):
        """Test for survey.models.SurveySubmission get_survey_answer/set_survey_answer"""
        submission = SurveySubmission()
        self.assertEquals(submission.get_survey_answer(), {})
        submission.set_survey_answer({})
        self.assertEquals(submission.get_survey_answer(), {})
