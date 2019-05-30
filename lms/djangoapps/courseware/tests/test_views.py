# coding=UTF-8
"""
Tests courseware views.py
"""
import cgi
from urllib import urlencode
import ddt
import json
import itertools
import pytz
import random
import unittest
from collections import OrderedDict
from datetime import datetime, timedelta
from HTMLParser import HTMLParser
from nose.plugins.attrib import attr
from freezegun import freeze_time

from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.test import TestCase
from django.test.client import RequestFactory
from django.test.client import Client
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.crypto import get_random_string
from mock import MagicMock, patch, create_autospec, Mock
from opaque_keys.edx.locations import Location, SlashSeparatedCourseKey
from pytz import UTC
from xblock.core import XBlock
from xblock.fields import String, Scope
from xblock.fragment import Fragment

import courseware.views as views
import shoppingcart
from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore
from biz.djangoapps.ga_achievement.models import BATCH_STATUS_STARTED, BATCH_STATUS_FINISHED, BATCH_STATUS_ERROR
from biz.djangoapps.ga_achievement.tests.factories import PlaybackBatchStatusFactory
from biz.djangoapps.ga_contract.tests.factories import ContractFactory, ContractDetailFactory
from biz.djangoapps.ga_organization.tests.factories import OrganizationFactory
from biz.djangoapps.util import datetime_utils
from certificates import api as certs_api
from certificates.models import CertificateStatuses, CertificateGenerationConfiguration
from certificates.tests.factories import GeneratedCertificateFactory
from course_modes.models import CourseMode
from course_modes.tests.factories import CourseModeFactory
from courseware.ga_progress_restriction import ProgressRestriction
from courseware.model_data import set_score
from courseware.testutils import RenderXBlockTestMixin
from courseware.tests.factories import (
    GaCourseScorerFactory, GaGlobalCourseCreatorFactory, StudentModuleFactory, PlaybackFinishFactory)
from courseware.user_state_client import DjangoXBlockUserStateClient
from edxmako.tests import mako_middleware_process_request
from ga_survey.tests.factories import SurveySubmissionFactory
from lms.djangoapps.courseware.tests.test_ga_mongo_utils import PlaybackFinishTestBase
from lms.djangoapps.courseware.ga_mongo_utils import PlaybackFinishStore
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from student.models import CourseEnrollment
from student.tests.factories import AdminFactory, UserFactory, CourseEnrollmentFactory, CourseEnrollmentAttributeFactory
from util.tests.test_date_utils import fake_ugettext, fake_pgettext
from util.url import reload_django_url_config
from util.views import ensure_valid_course_key
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import TEST_DATA_MIXED_TOY_MODULESTORE
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory, check_mongo_calls


@attr('shard_1')
class TestJumpTo(ModuleStoreTestCase):
    """
    Check the jumpto link for a course.
    """
    MODULESTORE = TEST_DATA_MIXED_TOY_MODULESTORE

    def setUp(self):
        super(TestJumpTo, self).setUp()
        # Use toy course from XML
        self.course_key = SlashSeparatedCourseKey('edX', 'toy', '2012_Fall')

    def test_jumpto_invalid_location(self):
        location = self.course_key.make_usage_key(None, 'NoSuchPlace')
        # This is fragile, but unfortunately the problem is that within the LMS we
        # can't use the reverse calls from the CMS
        jumpto_url = '{0}/{1}/jump_to/{2}'.format('/courses', self.course_key.to_deprecated_string(), location.to_deprecated_string())
        response = self.client.get(jumpto_url)
        self.assertEqual(response.status_code, 404)

    @unittest.skip
    def test_jumpto_from_chapter(self):
        location = self.course_key.make_usage_key('chapter', 'Overview')
        jumpto_url = '{0}/{1}/jump_to/{2}'.format('/courses', self.course_key.to_deprecated_string(), location.to_deprecated_string())
        expected = 'courses/edX/toy/2012_Fall/courseware/Overview/'
        response = self.client.get(jumpto_url)
        self.assertRedirects(response, expected, status_code=302, target_status_code=302)

    @unittest.skip
    def test_jumpto_id(self):
        jumpto_url = '{0}/{1}/jump_to_id/{2}'.format('/courses', self.course_key.to_deprecated_string(), 'Overview')
        expected = 'courses/edX/toy/2012_Fall/courseware/Overview/'
        response = self.client.get(jumpto_url)
        self.assertRedirects(response, expected, status_code=302, target_status_code=302)

    def test_jumpto_from_section(self):
        course = CourseFactory.create()
        chapter = ItemFactory.create(category='chapter', parent_location=course.location)
        section = ItemFactory.create(category='sequential', parent_location=chapter.location)
        expected = 'courses/{course_id}/courseware/{chapter_id}/{section_id}/?{activate_block_id}'.format(
            course_id=unicode(course.id),
            chapter_id=chapter.url_name,
            section_id=section.url_name,
            activate_block_id=urlencode({'activate_block_id': unicode(section.location)})
        )
        jumpto_url = '{0}/{1}/jump_to/{2}'.format(
            '/courses',
            unicode(course.id),
            unicode(section.location),
        )
        response = self.client.get(jumpto_url)
        self.assertRedirects(response, expected, status_code=302, target_status_code=302)

    def test_jumpto_from_module(self):
        course = CourseFactory.create()
        chapter = ItemFactory.create(category='chapter', parent_location=course.location)
        section = ItemFactory.create(category='sequential', parent_location=chapter.location)
        vertical1 = ItemFactory.create(category='vertical', parent_location=section.location)
        vertical2 = ItemFactory.create(category='vertical', parent_location=section.location)
        module1 = ItemFactory.create(category='html', parent_location=vertical1.location)
        module2 = ItemFactory.create(category='html', parent_location=vertical2.location)

        expected = 'courses/{course_id}/courseware/{chapter_id}/{section_id}/1?{activate_block_id}'.format(
            course_id=unicode(course.id),
            chapter_id=chapter.url_name,
            section_id=section.url_name,
            activate_block_id=urlencode({'activate_block_id': unicode(module1.location)})
        )
        jumpto_url = '{0}/{1}/jump_to/{2}'.format(
            '/courses',
            unicode(course.id),
            unicode(module1.location),
        )
        response = self.client.get(jumpto_url)
        self.assertRedirects(response, expected, status_code=302, target_status_code=302)

        expected = 'courses/{course_id}/courseware/{chapter_id}/{section_id}/2?{activate_block_id}'.format(
            course_id=unicode(course.id),
            chapter_id=chapter.url_name,
            section_id=section.url_name,
            activate_block_id=urlencode({'activate_block_id': unicode(module2.location)})
        )
        jumpto_url = '{0}/{1}/jump_to/{2}'.format(
            '/courses',
            unicode(course.id),
            unicode(module2.location),
        )
        response = self.client.get(jumpto_url)
        self.assertRedirects(response, expected, status_code=302, target_status_code=302)

    def test_jumpto_from_nested_module(self):
        course = CourseFactory.create()
        chapter = ItemFactory.create(category='chapter', parent_location=course.location)
        section = ItemFactory.create(category='sequential', parent_location=chapter.location)
        vertical = ItemFactory.create(category='vertical', parent_location=section.location)
        nested_section = ItemFactory.create(category='sequential', parent_location=vertical.location)
        nested_vertical1 = ItemFactory.create(category='vertical', parent_location=nested_section.location)
        # put a module into nested_vertical1 for completeness
        ItemFactory.create(category='html', parent_location=nested_vertical1.location)
        nested_vertical2 = ItemFactory.create(category='vertical', parent_location=nested_section.location)
        module2 = ItemFactory.create(category='html', parent_location=nested_vertical2.location)

        # internal position of module2 will be 1_2 (2nd item withing 1st item)

        expected = 'courses/{course_id}/courseware/{chapter_id}/{section_id}/1?{activate_block_id}'.format(
            course_id=unicode(course.id),
            chapter_id=chapter.url_name,
            section_id=section.url_name,
            activate_block_id=urlencode({'activate_block_id': unicode(module2.location)})
        )
        jumpto_url = '{0}/{1}/jump_to/{2}'.format(
            '/courses',
            unicode(course.id),
            unicode(module2.location),
        )
        response = self.client.get(jumpto_url)
        self.assertRedirects(response, expected, status_code=302, target_status_code=302)

    def test_jumpto_id_invalid_location(self):
        location = Location('edX', 'toy', 'NoSuchPlace', None, None, None)
        jumpto_url = '{0}/{1}/jump_to_id/{2}'.format('/courses', self.course_key.to_deprecated_string(), location.to_deprecated_string())
        response = self.client.get(jumpto_url)
        self.assertEqual(response.status_code, 404)


@attr('shard_1')
@ddt.ddt
class ViewsTestCase(ModuleStoreTestCase):
    """
    Tests for views.py methods.
    """
    def setUp(self):
        super(ViewsTestCase, self).setUp()
        self.course = CourseFactory.create(display_name=u'teꜱᴛ course')
        self.chapter = ItemFactory.create(category='chapter', parent_location=self.course.location)
        self.section = ItemFactory.create(category='sequential', parent_location=self.chapter.location, due=datetime(2013, 9, 18, 11, 30, 00))
        self.vertical = ItemFactory.create(category='vertical', parent_location=self.section.location)
        self.component = ItemFactory.create(category='problem', parent_location=self.vertical.location)

        self.course_key = self.course.id
        self.password = '123456'
        self.user = UserFactory(username='dummy', password=self.password, email='test@mit.edu')
        self.date = datetime(2013, 1, 22, tzinfo=UTC)
        self.enrollment = CourseEnrollment.enroll(self.user, self.course_key)
        self.enrollment.created = self.date
        self.enrollment.save()
        self.request_factory = RequestFactory()
        chapter = 'Overview'
        self.chapter_url = '%s/%s/%s' % ('/courses', self.course_key, chapter)

        self.org = u"ꜱᴛᴀʀᴋ ɪɴᴅᴜꜱᴛʀɪᴇꜱ"
        self.org_html = "<p>'+Stark/Industries+'</p>"

    @unittest.skipUnless(settings.FEATURES.get('ENABLE_SHOPPING_CART'), "Shopping Cart not enabled in settings")
    @patch.dict(settings.FEATURES, {'ENABLE_PAID_COURSE_REGISTRATION': True})
    def test_course_about_in_cart(self):
        in_cart_span = '<span class="add-to-cart">'
        # don't mock this course due to shopping cart existence checking
        course = CourseFactory.create(org="new", number="unenrolled", display_name="course")
        request = self.request_factory.get(reverse('about_course', args=[course.id.to_deprecated_string()]))
        request.user = AnonymousUser()
        mako_middleware_process_request(request)
        response = views.course_about(request, course.id.to_deprecated_string())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(in_cart_span, response.content)

        # authenticated user with nothing in cart
        request.user = self.user
        response = views.course_about(request, course.id.to_deprecated_string())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(in_cart_span, response.content)

        # now add the course to the cart
        cart = shoppingcart.models.Order.get_cart_for_user(self.user)
        shoppingcart.models.PaidCourseRegistration.add_to_order(cart, course.id)
        response = views.course_about(request, course.id.to_deprecated_string())
        self.assertEqual(response.status_code, 200)
        self.assertIn(in_cart_span, response.content)

    def test_user_groups(self):
        # depreciated function
        mock_user = MagicMock()
        mock_user.is_authenticated.return_value = False
        self.assertEqual(views.user_groups(mock_user), [])

    def test_get_current_child(self):
        self.assertIsNone(views.get_current_child(MagicMock()))
        mock_xmodule = MagicMock()
        mock_xmodule.position = -1
        mock_xmodule.get_display_items.return_value = ['one', 'two']
        self.assertEqual(views.get_current_child(mock_xmodule), 'one')
        mock_xmodule_2 = MagicMock()
        mock_xmodule_2.position = 3
        mock_xmodule_2.get_display_items.return_value = []
        self.assertIsNone(views.get_current_child(mock_xmodule_2))

    def test_redirect_to_course_position(self):
        mock_module = MagicMock()
        mock_module.descriptor.id = 'Underwater Basketweaving'
        mock_module.position = 3
        mock_module.get_display_items.return_value = []
        self.assertRaises(Http404, views.redirect_to_course_position,
                          mock_module, views.CONTENT_DEPTH)

    def test_invalid_course_id(self):
        response = self.client.get('/courses/MITx/3.091X/')
        self.assertEqual(response.status_code, 404)

    def test_incomplete_course_id(self):
        response = self.client.get('/courses/MITx/')
        self.assertEqual(response.status_code, 404)

    def test_index_invalid_position(self):
        request_url = '/'.join([
            '/courses',
            self.course.id.to_deprecated_string(),
            'courseware',
            self.chapter.location.name,
            self.section.location.name,
            'f'
        ])
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.get(request_url)
        self.assertEqual(response.status_code, 404)

    def test_unicode_handling_in_url(self):
        url_parts = [
            '/courses',
            self.course.id.to_deprecated_string(),
            'courseware',
            self.chapter.location.name,
            self.section.location.name,
            '1'
        ]
        self.client.login(username=self.user.username, password=self.password)
        for idx, val in enumerate(url_parts):
            url_parts_copy = url_parts[:]
            url_parts_copy[idx] = val + u'χ'
            request_url = '/'.join(url_parts_copy)
            response = self.client.get(request_url)
            self.assertEqual(response.status_code, 404)

    def test_registered_for_course(self):
        self.assertFalse(views.registered_for_course('Basketweaving', None))
        mock_user = MagicMock()
        mock_user.is_authenticated.return_value = False
        self.assertFalse(views.registered_for_course('dummy', mock_user))
        mock_course = MagicMock()
        mock_course.id = self.course_key
        self.assertTrue(views.registered_for_course(mock_course, self.user))

    @override_settings(PAID_COURSE_REGISTRATION_CURRENCY=["USD", "$"])
    def test_get_cosmetic_display_price(self):
        """
        Check that get_cosmetic_display_price() returns the correct price given its inputs.
        """
        registration_price = 99
        self.course.cosmetic_display_price = 10
        # Since registration_price is set, it overrides the cosmetic_display_price and should be returned
        self.assertEqual(views.get_cosmetic_display_price(self.course, registration_price), "$99")

        registration_price = 0
        # Since registration_price is not set, cosmetic_display_price should be returned
        self.assertEqual(views.get_cosmetic_display_price(self.course, registration_price), "$10")

        self.course.cosmetic_display_price = 0
        # Since both prices are not set, there is no price, thus "Free"
        self.assertEqual(views.get_cosmetic_display_price(self.course, registration_price), "Free")

    def test_jump_to_invalid(self):
        # TODO add a test for invalid location
        # TODO add a test for no data *
        request = self.request_factory.get(self.chapter_url)
        self.assertRaisesRegexp(Http404, 'Invalid course_key or usage_key', views.jump_to,
                                request, 'bar', ())

    @unittest.skip
    def test_no_end_on_about_page(self):
        # Toy course has no course end date or about/end_date blob
        self.verify_end_date('edX/toy/TT_2012_Fall')

    @unittest.skip
    def test_no_end_about_blob(self):
        # test_end has a course end date, no end_date HTML blob
        self.verify_end_date("edX/test_end/2012_Fall", "Sep 17, 2015")

    @unittest.skip
    def test_about_blob_end_date(self):
        # test_about_blob_end_date has both a course end date and an end_date HTML blob.
        # HTML blob wins
        self.verify_end_date("edX/test_about_blob_end_date/2012_Fall", "Learning never ends")

    def verify_end_date(self, course_id, expected_end_text=None):
        """
        Visits the about page for `course_id` and tests that both the text "Classes End", as well
        as the specified `expected_end_text`, is present on the page.

        If `expected_end_text` is None, verifies that the about page *does not* contain the text
        "Classes End".
        """
        request = self.request_factory.get("foo")
        request.user = self.user

        # TODO: Remove the dependency on MakoMiddleware (by making the views explicitly supply a RequestContext)
        mako_middleware_process_request(request)

        result = views.course_about(request, course_id)
        if expected_end_text is not None:
            self.assertContains(result, "Classes End")
            self.assertContains(result, expected_end_text)
        else:
            self.assertNotContains(result, "Classes End")

    def test_submission_history_accepts_valid_ids(self):
        # log into a staff account
        admin = AdminFactory()

        self.client.login(username=admin.username, password='test')

        url = reverse('submission_history', kwargs={
            'course_id': self.course_key.to_deprecated_string(),
            'student_username': 'dummy',
            'location': self.component.location.to_deprecated_string(),
        })
        response = self.client.get(url)
        # Tests that we do not get an "Invalid x" response when passing correct arguments to view
        self.assertFalse('Invalid' in response.content)

    def test_submission_history_xss(self):
        # log into a staff account
        admin = AdminFactory()

        self.client.login(username=admin.username, password='test')

        # try it with an existing user and a malicious location
        url = reverse('submission_history', kwargs={
            'course_id': self.course_key.to_deprecated_string(),
            'student_username': 'dummy',
            'location': '<script>alert("hello");</script>'
        })
        response = self.client.get(url)
        self.assertFalse('<script>' in response.content)

        # try it with a malicious user and a non-existent location
        url = reverse('submission_history', kwargs={
            'course_id': self.course_key.to_deprecated_string(),
            'student_username': '<script>alert("hello");</script>',
            'location': 'dummy'
        })
        response = self.client.get(url)
        self.assertFalse('<script>' in response.content)

    def test_submission_history_contents(self):
        # log into a staff account
        admin = AdminFactory.create()

        self.client.login(username=admin.username, password='test')

        usage_key = self.course_key.make_usage_key('problem', 'test-history')
        state_client = DjangoXBlockUserStateClient(admin)

        # store state via the UserStateClient
        state_client.set(
            username=admin.username,
            block_key=usage_key,
            state={'field_a': 'x', 'field_b': 'y'}
        )

        set_score(admin.id, usage_key, 0, 3)

        state_client.set(
            username=admin.username,
            block_key=usage_key,
            state={'field_a': 'a', 'field_b': 'b'}
        )
        set_score(admin.id, usage_key, 3, 3)

        url = reverse('submission_history', kwargs={
            'course_id': unicode(self.course_key),
            'student_username': admin.username,
            'location': unicode(usage_key),
        })
        response = self.client.get(url)
        response_content = HTMLParser().unescape(response.content.decode('utf-8'))

        # We have update the state 4 times: twice to change content, and twice
        # to set the scores. We'll check that the identifying content from each is
        # displayed (but not the order), and also the indexes assigned in the output
        # #1 - #4

        self.assertIn('#1', response_content)
        self.assertIn(json.dumps({'field_a': 'a', 'field_b': 'b'}, sort_keys=True, indent=2), response_content)
        self.assertIn("Score: 0.0 / 3.0", response_content)
        self.assertIn(json.dumps({'field_a': 'x', 'field_b': 'y'}, sort_keys=True, indent=2), response_content)
        self.assertIn("Score: 3.0 / 3.0", response_content)
        self.assertIn('#4', response_content)

    def test_submission_history_contents_with_ga_course_scorer(self):
        # log into a GaCourseScorer
        ga_course_scorer = GaCourseScorerFactory(course_key=self.course.id)

        self.client.login(username=ga_course_scorer.username, password='test')

        usage_key = self.course_key.make_usage_key('problem', 'test-history')
        state_client = DjangoXBlockUserStateClient(ga_course_scorer)

        # store state via the UserStateClient
        state_client.set(
            username=ga_course_scorer.username,
            block_key=usage_key,
            state={'field_a': 'x', 'field_b': 'y'}
        )

        set_score(ga_course_scorer.id, usage_key, 0, 3)

        state_client.set(
            username=ga_course_scorer.username,
            block_key=usage_key,
            state={'field_a': 'a', 'field_b': 'b'}
        )
        set_score(ga_course_scorer.id, usage_key, 3, 3)

        url = reverse('submission_history', kwargs={
            'course_id': unicode(self.course_key),
            'student_username': ga_course_scorer.username,
            'location': unicode(usage_key),
        })
        response = self.client.get(url)
        response_content = HTMLParser().unescape(response.content.decode('utf-8'))

        # We have update the state 4 times: twice to change content, and twice
        # to set the scores. We'll check that the identifying content from each is
        # displayed (but not the order), and also the indexes assigned in the output
        # #1 - #4

        self.assertIn('#1', response_content)
        self.assertIn(json.dumps({'field_a': 'a', 'field_b': 'b'}, sort_keys=True, indent=2), response_content)
        self.assertIn("Score: 0.0 / 3.0", response_content)
        self.assertIn(json.dumps({'field_a': 'x', 'field_b': 'y'}, sort_keys=True, indent=2), response_content)
        self.assertIn("Score: 3.0 / 3.0", response_content)
        self.assertIn('#4', response_content)

    @ddt.data(('America/New_York', -5),  # UTC - 5
              ('Asia/Pyongyang', 9),  # UTC + 9
              ('Europe/London', 0),  # UTC
              ('Canada/Yukon', -8),  # UTC - 8
              ('Europe/Moscow', 4))  # UTC + 3 + 1 for daylight savings
    @ddt.unpack
    @freeze_time('2012-01-01')
    def test_submission_history_timezone(self, timezone, hour_diff):
        with (override_settings(TIME_ZONE=timezone)):
            course = CourseFactory.create()
            course_key = course.id
            client = Client()
            admin = AdminFactory.create()
            client.login(username=admin.username, password='test')
            state_client = DjangoXBlockUserStateClient(admin)
            usage_key = course_key.make_usage_key('problem', 'test-history')
            state_client.set(
                username=admin.username,
                block_key=usage_key,
                state={'field_a': 'x', 'field_b': 'y'}
            )
            url = reverse('submission_history', kwargs={
                'course_id': unicode(course_key),
                'student_username': admin.username,
                'location': unicode(usage_key),
            })
            response = client.get(url)
            response_content = HTMLParser().unescape(response.content)
            expected_time = datetime.now() + timedelta(hours=hour_diff)
            expected_tz = expected_time.strftime('%Z')
            self.assertIn(expected_tz, response_content)
            self.assertIn(str(expected_time), response_content)

    def _email_opt_in_checkbox(self, response, org_name_string=None):
        """Check if the email opt-in checkbox appears in the response content."""
        checkbox_html = '<input id="email-opt-in" type="checkbox" name="opt-in" class="email-opt-in" value="true" checked>'
        if org_name_string:
            # Verify that the email opt-in checkbox appears, and that the expected
            # organization name is displayed.
            self.assertContains(response, checkbox_html, html=True)
            self.assertContains(response, org_name_string)
        else:
            # Verify that the email opt-in checkbox does not appear
            self.assertNotContains(response, checkbox_html, html=True)

    def test_financial_assistance_page(self):
        self.client.login(username=self.user.username, password=self.password)
        url = reverse('financial_assistance')
        response = self.client.get(url)
        # This is a static page, so just assert that it is returned correctly
        self.assertEqual(response.status_code, 200)
        self.assertIn('Financial Assistance Application', response.content)

    def test_financial_assistance_form(self):
        non_verified_course = CourseFactory.create().id
        verified_course_verified_track = CourseFactory.create().id
        verified_course_audit_track = CourseFactory.create().id
        verified_course_deadline_passed = CourseFactory.create().id
        unenrolled_course = CourseFactory.create().id

        enrollments = (
            (non_verified_course, CourseMode.AUDIT, None),
            (verified_course_verified_track, CourseMode.VERIFIED, None),
            (verified_course_audit_track, CourseMode.AUDIT, None),
            (verified_course_deadline_passed, CourseMode.AUDIT, datetime.now(UTC) - timedelta(days=1))
        )
        for course, mode, expiration in enrollments:
            CourseModeFactory(mode_slug=CourseMode.AUDIT, course_id=course)
            if course != non_verified_course:
                CourseModeFactory(mode_slug=CourseMode.VERIFIED, course_id=course, expiration_datetime=expiration)
            CourseEnrollmentFactory(course_id=course, user=self.user, mode=mode)

        self.client.login(username=self.user.username, password=self.password)
        url = reverse('financial_assistance_form')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Ensure that the user can only apply for assistance in
        # courses which have a verified mode which hasn't expired yet,
        # where the user is not already enrolled in verified mode
        self.assertIn(str(verified_course_audit_track), response.content)
        for course in (
                non_verified_course,
                verified_course_verified_track,
                verified_course_deadline_passed,
                unenrolled_course
        ):
            self.assertNotIn(str(course), response.content)

    def _submit_financial_assistance_form(self, data):
        """Submit a financial assistance request."""
        self.client.login(username=self.user.username, password=self.password)
        url = reverse('submit_financial_assistance_request')
        return self.client.post(url, json.dumps(data), content_type='application/json')

    @patch.object(views, '_record_feedback_in_zendesk')
    def test_submit_financial_assistance_request(self, mock_record_feedback):
        username = self.user.username
        course = unicode(self.course_key)
        legal_name = 'Jesse Pinkman'
        country = 'United States'
        income = '1234567890'
        reason_for_applying = "It's just basic chemistry, yo."
        goals = "I don't know if it even matters, but... work with my hands, I guess."
        effort = "I'm done, okay? You just give me my money, and you and I, we're done."
        data = {
            'username': username,
            'course': course,
            'name': legal_name,
            'email': self.user.email,
            'country': country,
            'income': income,
            'reason_for_applying': reason_for_applying,
            'goals': goals,
            'effort': effort,
            'mktg-permission': False,
        }
        response = self._submit_financial_assistance_form(data)
        self.assertEqual(response.status_code, 204)

        __, ___, ticket_subject, ticket_body, tags, additional_info = mock_record_feedback.call_args[0]
        mocked_kwargs = mock_record_feedback.call_args[1]
        group_name = mocked_kwargs['group_name']
        require_update = mocked_kwargs['require_update']
        private_comment = '\n'.join(additional_info.values())
        for info in (country, income, reason_for_applying, goals, effort, username, legal_name, course):
            self.assertIn(info, private_comment)

        self.assertEqual(additional_info['Allowed for marketing purposes'], 'No')

        self.assertEqual(
            ticket_subject,
            u'Financial assistance request for learner {username} in course {course}'.format(
                username=username,
                course=self.course.display_name
            )
        )
        self.assertDictContainsSubset({'course_id': course}, tags)
        self.assertIn('Client IP', additional_info)
        self.assertEqual(group_name, 'Financial Assistance')
        self.assertTrue(require_update)

    @patch.object(views, '_record_feedback_in_zendesk', return_value=False)
    def test_zendesk_submission_failed(self, _mock_record_feedback):
        response = self._submit_financial_assistance_form({
            'username': self.user.username,
            'course': unicode(self.course.id),
            'name': '',
            'email': '',
            'country': '',
            'income': '',
            'reason_for_applying': '',
            'goals': '',
            'effort': '',
            'mktg-permission': False,
        })
        self.assertEqual(response.status_code, 500)

    @ddt.data(
        ({}, 400),
        ({'username': 'wwhite'}, 403),
        ({'username': 'dummy', 'course': 'bad course ID'}, 400)
    )
    @ddt.unpack
    def test_submit_financial_assistance_errors(self, data, status):
        response = self._submit_financial_assistance_form(data)
        self.assertEqual(response.status_code, status)

    def test_financial_assistance_login_required(self):
        for url in (
                reverse('financial_assistance'),
                reverse('financial_assistance_form'),
                reverse('submit_financial_assistance_request')
        ):
            response = self.client.get(url)
            self.assertRedirects(response, reverse('signin_user') + '?next=' + url)


@attr('shard_1')
# setting TIME_ZONE_DISPLAYED_FOR_DEADLINES explicitly
@override_settings(TIME_ZONE_DISPLAYED_FOR_DEADLINES="UTC")
class BaseDueDateTests(ModuleStoreTestCase):
    """
    Base class that verifies that due dates are rendered correctly on a page
    """
    __test__ = False

    def get_text(self, course):
        """Return the rendered text for the page to be verified"""
        raise NotImplementedError

    def set_up_course(self, **course_kwargs):
        """
        Create a stock course with a specific due date.

        :param course_kwargs: All kwargs are passed to through to the :class:`CourseFactory`
        """
        course = CourseFactory.create(**course_kwargs)
        chapter = ItemFactory.create(category='chapter', parent_location=course.location)
        section = ItemFactory.create(category='sequential', parent_location=chapter.location, due=datetime(2013, 9, 18, 11, 30, 00))
        vertical = ItemFactory.create(category='vertical', parent_location=section.location)
        ItemFactory.create(category='problem', parent_location=vertical.location)

        course = modulestore().get_course(course.id)
        self.assertIsNotNone(course.get_children()[0].get_children()[0].due)
        CourseEnrollmentFactory(user=self.user, course_id=course.id)
        return course

    def setUp(self):
        super(BaseDueDateTests, self).setUp()
        self.request_factory = RequestFactory()
        self.user = UserFactory.create()
        self.request = self.request_factory.get("foo")
        self.request.user = self.user

        self.time_with_tz = "due Sep 18, 2013 at 11:30 UTC"
        self.time_without_tz = "due Sep 18, 2013 at 11:30"

    def test_backwards_compatability(self):
        # The test course being used has show_timezone = False in the policy file
        # (and no due_date_display_format set). This is to test our backwards compatibility--
        # in course_module's init method, the date_display_format will be set accordingly to
        # remove the timezone.
        course = self.set_up_course(due_date_display_format=None, show_timezone=False)
        text = self.get_text(course)
        self.assertIn(self.time_without_tz, text)
        self.assertNotIn(self.time_with_tz, text)
        # Test that show_timezone has been cleared (which means you get the default value of True).
        self.assertTrue(course.show_timezone)

    def test_defaults(self):
        course = self.set_up_course()
        text = self.get_text(course)
        self.assertIn(self.time_with_tz, text)

    def test_format_none(self):
        # Same for setting the due date to None
        course = self.set_up_course(due_date_display_format=None)
        text = self.get_text(course)
        self.assertIn(self.time_with_tz, text)

    def test_format_plain_text(self):
        # plain text due date
        course = self.set_up_course(due_date_display_format="foobar")
        text = self.get_text(course)
        self.assertNotIn(self.time_with_tz, text)
        self.assertIn("due foobar", text)

    def test_format_date(self):
        # due date with no time
        course = self.set_up_course(due_date_display_format=u"%b %d %y")
        text = self.get_text(course)
        self.assertNotIn(self.time_with_tz, text)
        self.assertIn("due Sep 18 13", text)

    def test_format_hidden(self):
        # hide due date completely
        course = self.set_up_course(due_date_display_format=u"")
        text = self.get_text(course)
        self.assertNotIn("due ", text)

    def test_format_invalid(self):
        # improperly formatted due_date_display_format falls through to default
        # (value of show_timezone does not matter-- setting to False to make that clear).
        course = self.set_up_course(due_date_display_format=u"%%%", show_timezone=False)
        text = self.get_text(course)
        self.assertNotIn("%%%", text)
        self.assertIn(self.time_with_tz, text)


class TestProgressDueDate(BaseDueDateTests):
    """
    Test that the progress page displays due dates correctly
    """
    __test__ = True

    def get_text(self, course):
        """ Returns the HTML for the progress page """

        mako_middleware_process_request(self.request)
        return views.progress(self.request, course_id=course.id.to_deprecated_string(), student_id=self.user.id).content


class TestAccordionDueDate(BaseDueDateTests):
    """
    Test that the accordion page displays due dates correctly
    """
    __test__ = True

    def get_text(self, course):
        """ Returns the HTML for the accordion """
        progress_restriction = ProgressRestriction(course.id, self.user, None)

        return views.render_accordion(
            self.request.user, self.request, course,
            unicode(course.get_children()[0].scope_ids.usage_id), None, None, progress_restriction
        )


@attr('shard_1')
class StartDateTests(ModuleStoreTestCase):
    """
    Test that start dates are properly localized and displayed on the student
    dashboard.
    """

    def setUp(self):
        super(StartDateTests, self).setUp()
        self.request_factory = RequestFactory()
        self.user = UserFactory.create()
        self.request = self.request_factory.get("foo")
        self.request.user = self.user

    def set_up_course(self):
        """
        Create a stock course with a specific due date.

        :param course_kwargs: All kwargs are passed to through to the :class:`CourseFactory`
        """
        course = CourseFactory.create(start=datetime(2013, 9, 16, 7, 17, 28))
        course = modulestore().get_course(course.id)
        return course

    def get_about_text(self, course_key):
        """
        Get the text of the /about page for the course.
        """
        text = views.course_about(self.request, course_key.to_deprecated_string()).content
        return text

    @patch('util.date_utils.pgettext', fake_pgettext(translations={
        ("abbreviated month name", "Sep"): "SEPTEMBER",
    }))
    @patch('util.date_utils.ugettext', fake_ugettext(translations={
        "SHORT_DATE_FORMAT": "%Y-%b-%d",
    }))
    @unittest.skip("It does not exist in the template of gacco")
    def test_format_localized_in_studio_course(self):
        course = self.set_up_course()
        text = self.get_about_text(course.id)
        # The start date is set in the set_up_course function above.
        self.assertIn("2013-SEPTEMBER-16", text)

    @patch('util.date_utils.pgettext', fake_pgettext(translations={
        ("abbreviated month name", "Jul"): "JULY",
    }))
    @patch('util.date_utils.ugettext', fake_ugettext(translations={
        "SHORT_DATE_FORMAT": "%Y-%b-%d",
    }))
    @unittest.skip
    def test_format_localized_in_xml_course(self):
        text = self.get_about_text(SlashSeparatedCourseKey('edX', 'toy', 'TT_2012_Fall'))
        # The start date is set in common/test/data/two_toys/policies/TT_2012_Fall/policy.json
        self.assertIn("2015-JULY-17", text)


@attr('shard_1')
@ddt.ddt
class ProgressPageTests(ModuleStoreTestCase):
    """
    Tests that verify that the progress page works correctly.
    """

    def setUp(self):
        super(ProgressPageTests, self).setUp()
        self.request_factory = RequestFactory()
        self.user = UserFactory.create()
        self.request = self.request_factory.get("foo")
        self.request.user = self.user

        mako_middleware_process_request(self.request)

        self.setup_course(self_paced=True)

    def setup_course(self, **options):
        """Create the test course."""
        course = CourseFactory.create(
            start=datetime(2013, 9, 16, 7, 17, 28),
            grade_cutoffs={u'çü†øƒƒ': 0.75, 'Pass': 0.5},
            **options
        )

        self.course = modulestore().get_course(course.id)
        CourseEnrollmentFactory(user=self.user, course_id=self.course.id)

        self.chapter = ItemFactory.create(category='chapter', parent_location=self.course.location)
        self.section = ItemFactory.create(category='sequential', parent_location=self.chapter.location)
        self.vertical = ItemFactory.create(category='vertical', parent_location=self.section.location)

    @ddt.data('"><script>alert(1)</script>', '<script>alert(1)</script>', '</script><script>alert(1)</script>')
    def test_progress_page_xss_prevent(self, malicious_code):
        """
        Test that XSS attack is prevented
        """
        resp = views.progress(self.request, course_id=unicode(self.course.id), student_id=self.user.id)
        self.assertEqual(resp.status_code, 200)
        # Test that malicious code does not appear in html
        self.assertNotIn(malicious_code, resp.content)

    def test_pure_ungraded_xblock(self):
        ItemFactory.create(category='acid', parent_location=self.vertical.location)

        resp = views.progress(self.request, course_id=self.course.id.to_deprecated_string())
        self.assertEqual(resp.status_code, 200)

    @ddt.data(ModuleStoreEnum.Type.mongo, ModuleStoreEnum.Type.split)
    def test_student_progress_with_valid_and_invalid_id(self, default_store):
        """
         Check that invalid 'student_id' raises Http404 for both old mongo and
         split mongo courses.
        """

        # Create new course with respect to 'default_store'
        self.course = CourseFactory.create(default_store=default_store)

        # Invalid Student Ids (Integer and Non-int)
        invalid_student_ids = [
            991021,
            'azU3N_8$',
        ]
        for invalid_id in invalid_student_ids:

            self.assertRaises(
                Http404, views.progress,
                self.request,
                course_id=unicode(self.course.id),
                student_id=invalid_id
            )

        # Enroll student into course
        CourseEnrollment.enroll(self.user, self.course.id)
        resp = views.progress(self.request, course_id=self.course.id.to_deprecated_string(), student_id=self.user.id)
        # Assert that valid 'student_id' returns 200 status
        self.assertEqual(resp.status_code, 200)

    def test_non_asci_grade_cutoffs(self):
        resp = views.progress(self.request, course_id=self.course.id.to_deprecated_string())

        self.assertEqual(resp.status_code, 200)

    def test_generate_cert_config(self):
        resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertNotContains(resp, 'Request Certificate')

        # Enable the feature, but do not enable it for this course
        CertificateGenerationConfiguration(enabled=True).save()
        resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertNotContains(resp, 'Request Certificate')

        # Enable certificate generation for this course
        certs_api.set_cert_generation_enabled(self.course.id, True)
        resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertNotContains(resp, 'Request Certificate')

    @patch.dict('django.conf.settings.FEATURES', {'CERTIFICATES_HTML_VIEW': True})
    @patch('courseware.grades.grade', Mock(return_value={'grade': 'Pass', 'percent': 0.75, 'section_breakdown': [],
                                                         'grade_breakdown': []}))
    def test_view_certificate_link(self):
        """
        If certificate web view is enabled then certificate web view button should appear for user who certificate is
        available/generated
        """
        certificate = GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            download_url="http://www.example.com/certificate.pdf",
            mode='honor'
        )

        # Enable the feature, but do not enable it for this course
        CertificateGenerationConfiguration(enabled=True).save()

        # Enable certificate generation for this course
        certs_api.set_cert_generation_enabled(self.course.id, True)

        #course certificate configurations
        certificates = [
            {
                'id': 1,
                'name': 'Name 1',
                'description': 'Description 1',
                'course_title': 'course_title_1',
                'signatories': [],
                'version': 1,
                'is_active': True
            }
        ]

        self.course.certificates = {'certificates': certificates}
        self.course.cert_html_view_enabled = True
        self.course.save()
        self.store.update_item(self.course, self.user.id)

        resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertContains(resp, u"View Certificate")

        self.assertContains(resp, u"You can download your certificate")
        cert_url = certs_api.get_certificate_url(course_id=self.course.id, uuid=certificate.verify_uuid)
        self.assertContains(resp, cert_url)

        # when course certificate is not active
        certificates[0]['is_active'] = False
        self.store.update_item(self.course, self.user.id)

        resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertNotContains(resp, u"View Your Certificate")
        self.assertNotContains(resp, u"You can now view your certificate")
        self.assertContains(resp, u"We're creating your certificate.")

    @patch.dict('django.conf.settings.FEATURES', {'CERTIFICATES_HTML_VIEW': False})
    @patch('courseware.grades.grade', Mock(return_value={'grade': 'Pass', 'percent': 0.75, 'section_breakdown': [],
                                                         'grade_breakdown': []}))
    def test_view_certificate_link_hidden(self):
        """
        If certificate web view is disabled then certificate web view button should not appear for user who certificate
        is available/generated
        """
        GeneratedCertificateFactory.create(
            user=self.user,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            download_url="http://www.example.com/certificate.pdf",
            mode='honor'
        )

        # Enable the feature, but do not enable it for this course
        CertificateGenerationConfiguration(enabled=True).save()

        # Enable certificate generation for this course
        certs_api.set_cert_generation_enabled(self.course.id, True)

        resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertContains(resp, u"Download Your Certificate")

    @ddt.data(
        *itertools.product(((71, 5, True), (46, 5, False)), (True, False))
    )
    @ddt.unpack
    def test_query_counts(self, (sql_calls, mongo_calls, self_paced), self_paced_enabled):
        """
        Test that query counts is as expected for self-paced and instructor-paced courses.

        This case is for 'audit' student, and SQL call counts differ between self-paced and instructor-paced
        because we did not cherry-pick 6fe063821414d3f4021a23000cb69702a1dfe8ae.
        We want even 'audit' student can see a certificate generation button in the progress page.
        """
        SelfPacedConfiguration(enabled=self_paced_enabled).save()
        self.setup_course(self_paced=self_paced)
        with self.assertNumQueries(sql_calls), check_mongo_calls(mongo_calls):
            resp = views.progress(self.request, course_id=unicode(self.course.id))
        self.assertEqual(resp.status_code, 200)


@attr('shard_1')
class PlaybackPageTests(ModuleStoreTestCase):
    """
    Tests that verify that the playback page works correctly.
    """

    def setUp(self):
        super(PlaybackPageTests, self).setUp()
        self.request_factory = RequestFactory()
        self.user = UserFactory.create()
        self.request = self.request_factory.get('foo')
        self.request.user = self.user
        mako_middleware_process_request(self.request)

        self.gacco_org = OrganizationFactory.create(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=UserFactory.create(),
        )
        self._create_course()
        self._create_org()
        self._create_contract()
        self._create_contract_detail()
        self.playback_store = PlaybackStore(self.contract.id, unicode(self.course.id))

        self.utc_datetime = datetime(2018, 7, 1, 9, 58, 30, 0, tzinfo=pytz.utc)
        self.utc_datetime_update = datetime(2018, 7, 17, 10, 58, 30, 0, tzinfo=pytz.utc)

    def tearDown(self):
        self.playback_store.remove_documents()

    def _create_course(self):
        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        CourseEnrollmentFactory(user=self.user, course_id=self.course.id)

        self.chapter_x_name = get_random_string(20)
        self.chapter_y_name = get_random_string(20)
        self.section_x_name = get_random_string(20)
        self.section_y_name = get_random_string(20)
        self.vertical_x1_name = get_random_string(20)
        self.vertical_x2_name = get_random_string(20)
        self.vertical_y1_name = get_random_string(20)

        self.chapter_x = ItemFactory.create(category='chapter',
                                            parent=self.course,
                                            display_name=self.chapter_x_name)
        self.chapter_y = ItemFactory.create(category='chapter',
                                            parent=self.course,
                                            display_name=self.chapter_y_name)
        self.section_x = ItemFactory.create(category='sequential',
                                            parent=self.chapter_x,
                                            display_name=self.section_x_name)
        self.section_y = ItemFactory.create(category='sequential',
                                            parent=self.chapter_y,
                                            display_name=self.section_y_name)
        self.vertical_x1 = ItemFactory.create(category='vertical',
                                              parent=self.section_x,
                                              display_name=self.vertical_x1_name)
        self.vertical_x2 = ItemFactory.create(category='vertical',
                                              parent=self.section_x,
                                              display_name=self.vertical_x2_name)
        self.vertical_y1 = ItemFactory.create(category='vertical',
                                              parent=self.section_y,
                                              display_name=self.vertical_y1_name)

    def _create_org(self):
        self.org_a = OrganizationFactory.create(
            org_name='org_a',
            org_code='org_a',
            creator_org=self.gacco_org,
            created_by=UserFactory.create(),
        )

    def _create_contract(self):
        self.contract = ContractFactory.create(contract_name='contract_a',
                                               contractor_organization=self.org_a,
                                               owner_organization=self.gacco_org,
                                               created_by=self.user,
                                               invitation_code='invitation_code_a')

    def _create_contract_detail(self):
        return ContractDetailFactory.create(course_id=self.course.id, contract=self.contract)

    def _create_playback_data_cloumn(self):

        column = OrderedDict()
        column[PlaybackStore.FIELD_CONTRACT_ID] = self.contract.id
        column[PlaybackStore.FIELD_COURSE_ID] = unicode(self.course.id)
        column[PlaybackStore.FIELD_DOCUMENT_TYPE] = PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN
        column[PlaybackStore.FIELD_FULL_NAME] = PlaybackStore.COLUMN_TYPE__TEXT
        column[PlaybackStore.FIELD_USERNAME] = PlaybackStore.COLUMN_TYPE__TEXT
        column[PlaybackStore.FIELD_EMAIL] = PlaybackStore.COLUMN_TYPE__TEXT
        column[PlaybackStore.FIELD_STUDENT_STATUS] = PlaybackStore.COLUMN_TYPE__TEXT
        column[PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME] = PlaybackStore.COLUMN_TYPE__TIME
        column['{}{}{}'.format(self.chapter_x.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               self.vertical_x1.display_name)] = PlaybackStore.COLUMN_TYPE__TIME
        column['{}{}{}'.format(self.chapter_x.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               self.vertical_x2.display_name)] = PlaybackStore.COLUMN_TYPE__TIME
        column['{}{}{}'.format(self.chapter_x.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               PlaybackStore.FIELD_SECTION_PLAYBACK_TIME)] = PlaybackStore.COLUMN_TYPE__TIME
        column['{}{}{}'.format(self.chapter_y.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               self.vertical_y1.display_name)] = PlaybackStore.COLUMN_TYPE__TIME
        column['{}{}{}'.format(self.chapter_y.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               PlaybackStore.FIELD_SECTION_PLAYBACK_TIME)] = PlaybackStore.COLUMN_TYPE__TIME

        self.total_time = random.randint(500, 10000)
        self.vertical_x1_time = random.randint(500, 10000)
        self.vertical_x2_time = random.randint(500, 10000)
        self.chapter_x_total_time = random.randint(500, 10000)
        self.vertical_y1_time = random.randint(500, 10000)
        self.chapter_y_total_time = random.randint(500, 10000)

        record = OrderedDict()
        record[PlaybackStore.FIELD_CONTRACT_ID] = self.contract.id
        record[PlaybackStore.FIELD_COURSE_ID] = unicode(self.course.id)
        record[PlaybackStore.FIELD_DOCUMENT_TYPE] = PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD
        record[PlaybackStore.FIELD_FULL_NAME] = self.user.profile.name
        record[PlaybackStore.FIELD_USERNAME] = self.user.username
        record[PlaybackStore.FIELD_EMAIL] = self.user.email
        record[PlaybackStore.FIELD_STUDENT_STATUS] = PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED
        record[PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME] = self.total_time
        record['{}{}{}'.format(self.chapter_x.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               self.vertical_x1.display_name)] = self.vertical_x1_time
        record['{}{}{}'.format(self.chapter_x.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               self.vertical_x2.display_name)] = self.vertical_x2_time
        record['{}{}{}'.format(self.chapter_x.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               PlaybackStore.FIELD_SECTION_PLAYBACK_TIME)] = self.chapter_x_total_time
        record['{}{}{}'.format(self.chapter_y.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               self.vertical_y1.display_name)] = self.vertical_y1_time
        record['{}{}{}'.format(self.chapter_y.display_name,
                               PlaybackStore.FIELD_DELIMITER,
                               PlaybackStore.FIELD_SECTION_PLAYBACK_TIME)] = self.chapter_y_total_time

        self.playback_store.set_documents([column])
        self.playback_store.set_documents(record)

    def _create_batch_status(self, status, update_time):
        self.batch_status = PlaybackBatchStatusFactory.create(contract=self.contract,
                                                              course_id=unicode(self.course.id),
                                                              status=status,
                                                              student_count=1)
        self.batch_status.created = update_time
        self.batch_status.save()

    def test_success(self):
        self._create_batch_status(BATCH_STATUS_STARTED, self.utc_datetime)
        self._create_batch_status(BATCH_STATUS_FINISHED, self.utc_datetime_update)
        self._create_playback_data_cloumn()

        resp = views.playback(self.request, course_id=unicode(self.course.id))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, datetime_utils.to_jst(self.utc_datetime_update).strftime('%Y/%m/%d %H:%M'))
        self.assertContains(resp, BATCH_STATUS_FINISHED)
        self.assertContains(resp, self.chapter_x.display_name)
        self.assertContains(resp, '{} : {}'.format(self.vertical_x1.display_name, datetime_utils.seconds_to_time_format(self.vertical_x1_time)))
        self.assertContains(resp, '{} : {}'.format(self.vertical_x2.display_name, datetime_utils.seconds_to_time_format(self.vertical_x2_time)))
        self.assertContains(resp, '{} : {}'.format(PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, datetime_utils.seconds_to_time_format(self.chapter_x_total_time)))
        self.assertContains(resp, self.chapter_y.display_name)
        self.assertContains(resp, '{} : {}'.format(self.vertical_y1.display_name, datetime_utils.seconds_to_time_format(self.vertical_y1_time)))
        self.assertContains(resp, '{} : {}'.format(PlaybackStore.FIELD_SECTION_PLAYBACK_TIME, datetime_utils.seconds_to_time_format(self.chapter_y_total_time)))
        self.assertNotContains(resp, PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)

    def test_batch_status_error(self):
        self._create_batch_status(BATCH_STATUS_STARTED, self.utc_datetime)
        self._create_batch_status(BATCH_STATUS_ERROR, self.utc_datetime_update)
        self._create_playback_data_cloumn()

        resp = views.playback(self.request, course_id=unicode(self.course.id))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No data is available. Please contact us through the Help.")

    def test_no_record_in_batch_status(self):
        self._create_playback_data_cloumn()

        resp = views.playback(self.request, course_id=unicode(self.course.id))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No records")

    def test_no_record_in_playback(self):
        self._create_batch_status(BATCH_STATUS_STARTED, self.utc_datetime)
        self._create_batch_status(BATCH_STATUS_FINISHED, self.utc_datetime_update)

        resp = views.playback(self.request, course_id=unicode(self.course.id))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "The data will be reflected after the next day of student registration.")

    @patch.object(views, 'get_course_with_access')
    def test_student_id_invalid(self, mock_get_course_with_access):
        self._create_batch_status(BATCH_STATUS_STARTED, self.utc_datetime)
        self._create_batch_status(BATCH_STATUS_FINISHED, self.utc_datetime_update)
        self.batch_status.created = self.utc_datetime_update
        self.batch_status.save()
        self.request.user.id = 0

        with self.assertRaises(Http404):
            views.playback(self.request, course_id=unicode(self.course.id))


@attr('shard_1')
class AttendancePageTests(ModuleStoreTestCase, PlaybackFinishTestBase):
    """
    Tests that verify that the attendance page works correctly.
    """
    def setUp(self, **kwargs):
        super(AttendancePageTests, self).setUp()
        self.request_factory = RequestFactory()
        self.password = '1234'
        self.user = UserFactory.create(password=self.password)

        self.gacco_org = OrganizationFactory.create(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=UserFactory.create(),
        )

        """
        Set up course and module
        ---
        course
          |- chapter_x
          |   |- section_x1
          |   |  |- vertical_x11
          |   |  |    |- module_x11_problem1, module_x11_problem2, module_x11_problem3
          |   |  |- vertical_x12
          |   |  |    |- module_x12_video1, module_x12_video2, module_x12_video3
          |   |  |- vertical_x13
          |   |  |    |- module_x13_survey1
          |   |  |- vertical_x14
          |   |  |    |- module_x14_survey1
          |   |  |- vertical_x15
          |   |  |    |- module_x15_survey1
          |   |  |- vertical_x16
          |   |  |    |- module_x16_freetextresponse1, module_x16_freetextresponse2, module_x16_freetextresponse3
          |   |  |- vertical_x17
          |   |  |    |- module_x16_survey1, module_x16_survey2, module_x16_survey3

          |- chapter_y
          |   |- section_y1
        """
        self.course = CourseFactory.create(org='gacco', number='course', run='run1',
                                           metadata={
                                               'start': datetime(2000, 1, 1, 0, 0, 0),
                                               'end': datetime(2010, 1, 1, 0, 0, 0),
                                               'is_status_managed': True,
                                           })
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name="chapter_x",
                                            metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name="section_x1",
                                             metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})
        # vertical_x11
        self.vertical_x11 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x11")
        self.module_x11_problem1 = ItemFactory.create(
            category='problem', parent_location=self.vertical_x11.location, display_name='module_x11_problem1',
            metadata={'is_status_managed': True})
        self.module_x11_problem2 = ItemFactory.create(
            category='problem', parent_location=self.vertical_x11.location, display_name='module_x11_problem2',
            metadata={'is_status_managed': True})
        self.module_x11_problem3 = ItemFactory.create(
            category='problem', parent_location=self.vertical_x11.location, display_name='module_x11_problem3',
            metadata={'is_status_managed': False})
        # vertical_x12
        self.vertical_x12 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x12")
        self.module_x12_video1 = ItemFactory.create(
            category='video', parent_location=self.vertical_x12.location, display_name='module_x12_video1',
            metadata={'is_status_managed': True})
        self.module_x12_video2 = ItemFactory.create(
            category='video', parent_location=self.vertical_x12.location, display_name='module_x12_video2',
            metadata={'is_status_managed': True})
        self.module_x12_video3 = ItemFactory.create(
            category='video', parent_location=self.vertical_x12.location, display_name='module_x12_video3',
            metadata={'is_status_managed': False})
        # vertical_x13
        self.vertical_x13 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x13")
        self.vertical_x13_survey1 = ItemFactory.create(
            category='html', parent_location=self.vertical_x13.location, display_name='vertical_x13_survey1',
            metadata={'is_status_managed': True})
        # vertical_x14
        self.vertical_x14 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x14")
        self.vertical_x14_survey1 = ItemFactory.create(
            category='html', parent_location=self.vertical_x14.location, display_name='vertical_x14_survey1',
            metadata={'is_status_managed': True})
        # vertical_x15
        self.vertical_x15 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x15")
        self.vertical_x15_survey1 = ItemFactory.create(
            category='html', parent_location=self.vertical_x15.location, display_name='vertical_x15_survey1',
            metadata={'is_status_managed': False})
        # vertical_x16
        self.vertical_x16 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x16")
        self.module_x16_freetextresponse1 = ItemFactory.create(
            category='freetextresponse', parent_location=self.vertical_x16.location,
            display_name='module_x16_freetextresponse1', metadata={'is_status_managed': True})
        self.module_x16_freetextresponse2 = ItemFactory.create(
            category='freetextresponse', parent_location=self.vertical_x16.location,
            display_name='module_x16_freetextresponse2', metadata={'is_status_managed': True})
        self.module_x16_freetextresponse3 = ItemFactory.create(
            category='freetextresponse', parent_location=self.vertical_x16.location,
            display_name='module_x16_freetextresponse3', metadata={'is_status_managed': False})
        # vertical_x17
        self.vertical_x17 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x17")
        self.module_x17_survey1 = ItemFactory.create(
            category='survey', parent_location=self.vertical_x17.location, display_name='module_x17_survey1',
            metadata={'is_status_managed': True})
        self.module_x17_survey2 = ItemFactory.create(
            category='survey', parent_location=self.vertical_x17.location, display_name='module_x17_survey2',
            metadata={'is_status_managed': True})
        self.module_x17_survey3 = ItemFactory.create(
            category='survey', parent_location=self.vertical_x17.location, display_name='module_x17_survey3',
            metadata={'is_status_managed': False})
        # chapter_y
        self.chapter_y = ItemFactory.create(parent=self.course, category='chapter', display_name="chapter_y",
                                            metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})
        self.section_y1 = ItemFactory.create(parent=self.chapter_y, category='sequential', display_name="section_y1",
                                             metadata={'start': datetime(2000, 1, 1, 0, 0, 0)})

        self.enrollment = CourseEnrollmentFactory(user=self.user, course_id=self.course.id)
        # set request
        self.client.login(username=self.user.username, password=self.password)
        self.request = self.request_factory.get(reverse('attendance', args=[unicode(self.course.id)]))
        self.request.user = self.user
        mako_middleware_process_request(self.request)

    @freeze_time('2005-01-01 00:00:00')
    @patch('courseware.views.render_to_response', return_value=HttpResponse())
    def test_attendance_when_status_working(self, mock_render_to_response):
        # arrange
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem1.location, student=self.user,
            grade=1, max_grade=4, state=None)
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video1, status=True)])
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x13.location.block_id, user=self.user,
            survey_name=self.vertical_x13_survey1.display_name, survey_answer='')
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x16_freetextresponse1.location, student=self.user,
            module_type='freetextresponse', state='{"count_attempts": 1}')
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x17_survey1.location, student=self.user,
            module_type='survey', state='{"submissions_count": 1}')
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "2010-10-10T10:10:10.123456+00:00"}')
        # act
        views.attendance(self.request, self.course.id.to_deprecated_string())
        # assert
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[0], 'courseware/attendance.html')
        self.assertEqual(render_to_response_args[1]['course'].id, self.course.id)
        self.assertEqual(render_to_response_args[1]['student'], self.user)
        self.assertEqual(render_to_response_args[1]['display_status'], 'working')
        self.assertEqual(render_to_response_args[1]['course_details'], [
            {
                'name': self.chapter_x.display_name,
                'url_name': self.chapter_x.url_name,
                'is_display': True,
                'sections': [
                    {
                        'name': self.section_x1.display_name,
                        'url_name': self.section_x1.url_name,
                        'is_display': True,
                        'verticals': [
                            {
                                'name': self.vertical_x11.display_name,
                                'status': False,
                                'is_display': True,
                                'modules': [
                                    {'name': self.module_x11_problem1.display_name, 'status': True},
                                    {'name': self.module_x11_problem2.display_name, 'status': False}
                                ]
                            },
                            {
                                'name': self.vertical_x12.display_name,
                                'status': False,
                                'is_display': True,
                                'modules': [
                                    {'name': self.module_x12_video1.display_name, 'status': True},
                                    {'name': self.module_x12_video2.display_name, 'status': False}
                                ]
                            },
                            {
                                'name': self.vertical_x13.display_name,
                                'status': True,
                                'is_display': True,
                                'modules': [
                                    {'name': self.vertical_x13_survey1.display_name, 'status': True}
                                ]
                            },
                            {
                                'name': self.vertical_x14.display_name,
                                'status': False,
                                'is_display': True,
                                'modules': [
                                    {'name': self.vertical_x14_survey1.display_name, 'status': False}
                                ]
                            },
                            {
                                'name': self.vertical_x15.display_name,
                                'status': True,
                                'is_display': True,
                                'modules': []
                            },
                            {
                                'name': self.vertical_x16.display_name,
                                'status': False,
                                'is_display': True,
                                'modules': [
                                    {'name': self.module_x16_freetextresponse1.display_name, 'status': True},
                                    {'name': self.module_x16_freetextresponse2.display_name, 'status': False}
                                ]
                            },
                            {
                                'name': self.vertical_x17.display_name,
                                'status': False,
                                'is_display': True,
                                'modules': [
                                    {'name': self.module_x17_survey1.display_name, 'status': True},
                                    {'name': self.module_x17_survey2.display_name, 'status': False}
                                ]
                            }
                        ]
                    }
                ]
            },
            {
                'name': self.chapter_y.display_name,
                'url_name': self.chapter_y.url_name,
                'is_display': True,
                'sections': [
                    {
                        'name': self.section_y1.display_name,
                        'is_display': True,
                        'url_name': self.section_y1.url_name,
                        'verticals': []
                    }
                ]
            }
        ])

    @freeze_time('2005-01-01 00:00:00')
    @patch('courseware.views.render_to_response', return_value=HttpResponse())
    def test_attendance_when_status_completed(self, mock_render_to_response):
        # arrange
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem1.location, student=self.user,
            grade=1, max_grade=4, state=None)
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x11_problem2.location, student=self.user,
            grade=1, max_grade=4, state=None)
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video1, status=True)])
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x12_video2, status=True)])
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x13.location.block_id, user=self.user,
            survey_name=self.vertical_x13_survey1.display_name, survey_answer='')
        SurveySubmissionFactory.create(
            course_id=self.course.id, unit_id=self.vertical_x14.location.block_id, user=self.user,
            survey_name=self.vertical_x14_survey1.display_name, survey_answer='')
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x16_freetextresponse1.location, student=self.user,
            module_type='freetextresponse', state='{"count_attempts": 1}')
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x16_freetextresponse2.location, student=self.user,
            module_type='freetextresponse', state='{"count_attempts": 1}')
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x17_survey1.location, student=self.user,
            module_type='survey', state='{"submissions_count": 1}')
        StudentModuleFactory.create(
            course_id=self.course.id, module_state_key=self.module_x17_survey2.location, student=self.user,
            module_type='survey', state='{"submissions_count": 1}')
        CourseEnrollmentAttributeFactory.create(
            enrollment=self.enrollment, namespace='ga', name='attended_status',
            value='{"attended_date": "2010-10-10T10:10:10.123456+00:00",'
                  '"completed_date": "2010-10-10T10:10:10.123456+00:00"}')
        # act
        views.attendance(self.request, self.course.id.to_deprecated_string())
        # assert
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[1]['display_status'], 'completed')

    @patch('courseware.views.render_to_response', return_value=HttpResponse())
    def test_attendance_when_status_waiting(self, mock_render_to_response):
        # arrange
        self.course.end = datetime(2020, 1, 1, 0, 0, 0)
        self.update_course(self.course, self.user.id)
        # act
        views.attendance(self.request, self.course.id.to_deprecated_string())
        # assert
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[1]['display_status'], 'waiting')

    @patch('courseware.views.render_to_response', return_value=HttpResponse())
    def test_attendance_when_status_closing(self, mock_render_to_response):
        # arrange
        self.course.terminate_start = timezone.now() - timedelta(days=1)
        self.update_course(self.course, self.user.id)
        # act
        views.attendance(self.request, self.course.id.to_deprecated_string())
        # assert
        render_to_response_args = mock_render_to_response.call_args[0]
        self.assertEqual(render_to_response_args[1]['display_status'], 'closing')

@attr('shard_1')
class VerifyCourseKeyDecoratorTests(TestCase):
    """
    Tests for the ensure_valid_course_key decorator.
    """

    def setUp(self):
        super(VerifyCourseKeyDecoratorTests, self).setUp()

        self.request = RequestFactory().get("foo")
        self.valid_course_id = "edX/test/1"
        self.invalid_course_id = "edX/"

    def test_decorator_with_valid_course_id(self):
        mocked_view = create_autospec(views.course_about)
        view_function = ensure_valid_course_key(mocked_view)
        view_function(self.request, course_id=self.valid_course_id)
        self.assertTrue(mocked_view.called)

    def test_decorator_with_invalid_course_id(self):
        mocked_view = create_autospec(views.course_about)
        view_function = ensure_valid_course_key(mocked_view)
        self.assertRaises(Http404, view_function, self.request, course_id=self.invalid_course_id)
        self.assertFalse(mocked_view.called)


@attr('shard_1')
class IsCoursePassedTests(ModuleStoreTestCase):
    """
    Tests for the is_course_passed helper function
    """

    SUCCESS_CUTOFF = 0.5

    def setUp(self):
        super(IsCoursePassedTests, self).setUp()

        self.student = UserFactory()
        self.course = CourseFactory.create(
            org='edx',
            number='verified',
            display_name='Verified Course',
            grade_cutoffs={'cutoff': 0.75, 'Pass': self.SUCCESS_CUTOFF}
        )
        self.request = RequestFactory()
        self.request.user = self.student

    def test_user_fails_if_not_clear_exam(self):
        # If user has not grade then false will return
        self.assertFalse(views.is_course_passed(self.course, None, self.student, self.request))

    @patch('courseware.grades.grade', Mock(return_value={'percent': 0.9}))
    def test_user_pass_if_percent_appears_above_passing_point(self):
        # Mocking the grades.grade
        # If user has above passing marks then True will return
        self.assertTrue(views.is_course_passed(self.course, None, self.student, self.request))

    @patch('courseware.grades.grade', Mock(return_value={'percent': 0.2}))
    def test_user_fail_if_percent_appears_below_passing_point(self):
        # Mocking the grades.grade
        # If user has below passing marks then False will return
        self.assertFalse(views.is_course_passed(self.course, None, self.student, self.request))

    @patch('courseware.grades.grade', Mock(return_value={'percent': SUCCESS_CUTOFF}))
    def test_user_with_passing_marks_and_achieved_marks_equal(self):
        # Mocking the grades.grade
        # If user's achieved passing marks are equal to the required passing
        # marks then it will return True
        self.assertTrue(views.is_course_passed(self.course, None, self.student, self.request))


@attr('shard_1')
class GenerateUserCertTests(ModuleStoreTestCase):
    """
    Tests for the view function Generated User Certs
    """

    def setUp(self):
        super(GenerateUserCertTests, self).setUp()

        self.student = UserFactory(username='dummy', password='123456', email='test@mit.edu')
        self.course = CourseFactory.create(
            org='edx',
            number='verified',
            display_name='Verified Course',
            grade_cutoffs={'cutoff': 0.75, 'Pass': 0.5}
        )
        self.enrollment = CourseEnrollment.enroll(self.student, self.course.id, mode='honor')
        self.request = RequestFactory()
        self.client.login(username=self.student, password='123456')
        self.url = reverse('generate_user_cert', kwargs={'course_id': unicode(self.course.id)})

    def test_user_with_out_passing_grades(self):
        # If user has no grading then json will return failed message and badrequest code
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, HttpResponseBadRequest.status_code)
        self.assertIn("Your certificate will be available when you pass the course.", resp.content)

    @patch('courseware.grades.grade', Mock(return_value={'grade': 'Pass', 'percent': 0.75}))
    @override_settings(CERT_QUEUE='certificates', LMS_SEGMENT_KEY="foobar")
    def test_user_with_passing_grade(self):
        # If user has above passing grading then json will return cert generating message and
        # status valid code
        # mocking xqueue and analytics

        analytics_patcher = patch('courseware.views.analytics')
        mock_tracker = analytics_patcher.start()
        self.addCleanup(analytics_patcher.stop)

        with patch('capa.xqueue_interface.XQueueInterface.send_to_queue') as mock_send_to_queue:
            mock_send_to_queue.return_value = (0, "Successfully queued")
            resp = self.client.post(self.url)
            self.assertEqual(resp.status_code, 200)

            #Verify Google Analytics event fired after generating certificate
            mock_tracker.track.assert_called_once_with(  # pylint: disable=no-member
                self.student.id,  # pylint: disable=no-member
                'edx.bi.user.certificate.generate',
                {
                    'category': 'certificates',
                    'label': unicode(self.course.id)
                },

                context={
                    'ip': '127.0.0.1',
                    'Google Analytics':
                    {'clientId': None}
                }
            )
            mock_tracker.reset_mock()

    @patch('courseware.grades.grade', Mock(return_value={'grade': 'Pass', 'percent': 0.75}))
    def test_user_with_passing_existing_generating_cert(self):
        # If user has passing grade but also has existing generating cert
        # then json will return cert generating message with bad request code
        GeneratedCertificateFactory.create(
            user=self.student,
            course_id=self.course.id,
            status=CertificateStatuses.generating,
            mode='verified'
        )
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, HttpResponseBadRequest.status_code)
        self.assertIn("Certificate self-generation is not allowed because the task has started before.", resp.content)

    @patch('courseware.grades.grade', Mock(return_value={'grade': 'Pass', 'percent': 0.75}))
    @override_settings(CERT_QUEUE='certificates', LMS_SEGMENT_KEY="foobar")
    def test_user_with_passing_existing_downloadable_cert(self):
        # If user has already downloadable certificate
        # then json will return cert generating message with bad request code

        GeneratedCertificateFactory.create(
            user=self.student,
            course_id=self.course.id,
            status=CertificateStatuses.downloadable,
            mode='verified'
        )

        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, HttpResponseBadRequest.status_code)
        self.assertIn("Certificate self-generation is not allowed because the task has started before.", resp.content)

    @patch('courseware.grades.grade', Mock(return_value={'grade': 'Pass', 'percent': 0.75}))
    def test_user_with_passing_existing_error_cert(self):
        # If cert generation task failed and status is set to error
        # then json will return cert generating message with bad request code
        GeneratedCertificateFactory.create(
            user=self.student,
            course_id=self.course.id,
            status=CertificateStatuses.error,
            mode='verified'
        )
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, HttpResponseBadRequest.status_code)
        self.assertIn("Certificate self-generation is not allowed because the task has started before.", resp.content)

    def test_user_with_non_existing_course(self):
        # If try to access a course with valid key pattern then it will return
        # bad request code with course is not valid message
        resp = self.client.post('/courses/def/abc/in_valid/generate_user_cert')
        self.assertEqual(resp.status_code, HttpResponseBadRequest.status_code)
        self.assertIn("Course is not valid", resp.content)

    def test_user_with_invalid_course_id(self):
        # If try to access a course with invalid key pattern then 404 will return
        resp = self.client.post('/courses/def/generate_user_cert')
        self.assertEqual(resp.status_code, 404)

    def test_user_without_login_return_error(self):
        # If user try to access without login should see a bad request status code with message
        self.client.logout()
        resp = self.client.post(self.url)
        self.assertEqual(resp.status_code, HttpResponseBadRequest.status_code)
        self.assertIn("You must be signed in to {platform_name} to create a certificate.".format(
            platform_name=settings.PLATFORM_NAME
        ), resp.content)


class ActivateIDCheckerBlock(XBlock):
    """
    XBlock for checking for an activate_block_id entry in the render context.
    """
    # We don't need actual children to test this.
    has_children = False

    def student_view(self, context):
        """
        A student view that displays the activate_block_id context variable.
        """
        result = Fragment()
        if 'activate_block_id' in context:
            result.add_content(u"Activate Block ID: {block_id}</p>".format(block_id=context['activate_block_id']))
        return result


class ViewCheckerBlock(XBlock):
    """
    XBlock for testing user state in views.
    """
    has_children = True
    state = String(scope=Scope.user_state)

    def student_view(self, context):  # pylint: disable=unused-argument
        """
        A student_view that asserts that the ``state`` field for this block
        matches the block's usage_id.
        """
        msg = "{} != {}".format(self.state, self.scope_ids.usage_id)
        assert self.state == unicode(self.scope_ids.usage_id), msg
        fragments = self.runtime.render_children(self)
        result = Fragment(
            content=u"<p>ViewCheckerPassed: {}</p>\n{}".format(
                unicode(self.scope_ids.usage_id),
                "\n".join(fragment.content for fragment in fragments),
            )
        )
        return result


@attr('shard_1')
@ddt.ddt
class TestIndexView(ModuleStoreTestCase):
    """
    Tests of the courseware.index view.
    """

    @XBlock.register_temp_plugin(ViewCheckerBlock, 'view_checker')
    @ddt.data(ModuleStoreEnum.Type.mongo, ModuleStoreEnum.Type.split)
    def test_student_state(self, default_store):
        """
        Verify that saved student state is loaded for xblocks rendered in the index view.
        """
        user = UserFactory()

        with modulestore().default_store(default_store):
            course = CourseFactory.create()
            chapter = ItemFactory.create(parent=course, category='chapter')
            section = ItemFactory.create(parent=chapter, category='view_checker', display_name="Sequence Checker")
            vertical = ItemFactory.create(parent=section, category='view_checker', display_name="Vertical Checker")
            block = ItemFactory.create(parent=vertical, category='view_checker', display_name="Block Checker")

        for item in (section, vertical, block):
            StudentModuleFactory.create(
                student=user,
                course_id=course.id,
                module_state_key=item.scope_ids.usage_id,
                state=json.dumps({'state': unicode(item.scope_ids.usage_id)})
            )

        CourseEnrollmentFactory(user=user, course_id=course.id)

        request = RequestFactory().get(
            reverse(
                'courseware_section',
                kwargs={
                    'course_id': unicode(course.id),
                    'chapter': chapter.url_name,
                    'section': section.url_name,
                }
            )
        )
        request.user = user
        mako_middleware_process_request(request)

        # Trigger the assertions embedded in the ViewCheckerBlocks
        response = views.index(request, unicode(course.id), chapter=chapter.url_name, section=section.url_name)
        self.assertEquals(response.content.count("ViewCheckerPassed"), 3)

    @XBlock.register_temp_plugin(ActivateIDCheckerBlock, 'id_checker')
    def test_activate_block_id(self):
        user = UserFactory()

        course = CourseFactory.create()
        chapter = ItemFactory.create(parent=course, category='chapter')
        section = ItemFactory.create(parent=chapter, category='sequential', display_name="Sequence")
        vertical = ItemFactory.create(parent=section, category='vertical', display_name="Vertical")
        ItemFactory.create(parent=vertical, category='id_checker', display_name="ID Checker")

        CourseEnrollmentFactory(user=user, course_id=course.id)

        request = RequestFactory().get(
            reverse(
                'courseware_section',
                kwargs={
                    'course_id': unicode(course.id),
                    'chapter': chapter.url_name,
                    'section': section.url_name,
                }
            ) + '?activate_block_id=test_block_id'
        )
        request.user = user
        mako_middleware_process_request(request)

        response = views.index(request, unicode(course.id), chapter=chapter.url_name, section=section.url_name)
        self.assertIn("Activate Block ID: test_block_id", response.content)


class TestRenderXBlock(RenderXBlockTestMixin, ModuleStoreTestCase):
    """
    Tests for the courseware.render_xblock endpoint.
    This class overrides the get_response method, which is used by
    the tests defined in RenderXBlockTestMixin.
    """
    def setUp(self):
        reload_django_url_config()
        super(TestRenderXBlock, self).setUp()

    def get_response(self, url_encoded_params=None):
        """
        Overridable method to get the response from the endpoint that is being tested.
        """
        url = reverse('render_xblock', kwargs={"usage_key_string": unicode(self.html_block.location)})
        if url_encoded_params:
            url += '?' + url_encoded_params
        return self.client.get(url)


class TestRenderXBlockSelfPaced(TestRenderXBlock):
    """
    Test rendering XBlocks for a self-paced course. Relies on the query
    count assertions in the tests defined by RenderXBlockMixin.
    """

    def setUp(self):
        super(TestRenderXBlockSelfPaced, self).setUp()
        SelfPacedConfiguration(enabled=True).save()

    def course_options(self):
        return {'self_paced': True}


class TestVisibleStudioUrl(ModuleStoreTestCase):
    """
    Tests for the view studio url
    """
    def setUp(self):
        super(TestVisibleStudioUrl, self).setUp()
        self.course = CourseFactory.create()

    def test_get_studio_url(self):
        # Global staff
        self.assertIsNotNone(views._get_studio_url(self.user, self.course, 'course'))

        # GaGlobalCourseCreatorFactory
        ga_global_course_creator = GaGlobalCourseCreatorFactory()
        self.assertIsNone(views._get_studio_url(ga_global_course_creator, self.course, 'course'))

        # GaCourseScorer
        ga_course_scorer = GaCourseScorerFactory(course_key=self.course.id)
        self.assertIsNone(views._get_studio_url(ga_course_scorer, self.course, 'course'))


@attr('shard_1')
class FinishPlaybackMongoTests(ModuleStoreTestCase, PlaybackFinishTestBase):
    """
    Tests that verify that the finish_playback_mongo works correctly.
    """
    def setUp(self, **kwargs):
        super(FinishPlaybackMongoTests, self).setUp()
        self.request_factory = RequestFactory()
        self.password = '1234'
        self.user = UserFactory.create(password=self.password)

        self.gacco_org = OrganizationFactory.create(
            org_name='docomo gacco',
            org_code='gacco',
            creator_org_id=1,
            created_by=UserFactory.create(),
        )

        self.utc_datetime = datetime(2018, 7, 1, 9, 58, 30, 0, tzinfo=pytz.utc)
        self.utc_datetime_update = datetime(2018, 7, 17, 10, 58, 30, 0, tzinfo=pytz.utc)

        self.course = CourseFactory.create(org='gacco', number='course', run='run1')
        self.chapter_x = ItemFactory.create(parent=self.course, category='chapter', display_name="chapter_x")
        self.section_x1 = ItemFactory.create(parent=self.chapter_x, category='sequential', display_name="section_x1")
        # vertical_x11
        self.vertical_x11 = ItemFactory.create(parent=self.section_x1, category='vertical', display_name="vertical_x11")

        self.module_x11_video1 = ItemFactory.create(
            category='video', parent_location=self.vertical_x11.location, display_name='module_x11_video1',
            metadata={'is_status_managed': True})

        CourseEnrollmentFactory(user=self.user, course_id=self.course.id)

        self.client.login(username=self.user.username, password=self.password)
        self.request = self.request_factory.get(reverse('finish_playback_mongo', args=[unicode(self.course.id)]))
        self.request.user = self.user
        mako_middleware_process_request(self.request)

    def test_finish_playback_mongo_from_false_to_true(self):
        """
        Tests that verify that the finish_playback_mongo works correctly.
        Test Case
            button push: Yes
            find_result: True
            request_module_id: True
            before status: False
        Expected Results
            status: False -> True
        """
        self.course.is_status_managed = True
        self.update_course(self.course, self.user.id)

        self._url = reverse('finish_playback_mongo', kwargs={'course_id': unicode(self.course.id)})

        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=False)])

        before = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        response = self.client.post(self._url, data={'data': 'Yes',
                                                     'module_id': self.module_x11_video1.location.block_id})

        after = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before[0]['module_list'][0]['status'], False)
        self.assertEqual(after[0]['module_list'][0]['status'], True)
        self.assertNotEqual(before[0]['module_list'][0]['change_time'], after[0]['module_list'][0]['change_time'])

    def test_finish_playback_mongo_from_none_to_true_when_not_module_id(self):
        """
        Tests that verify that the finish_playback_mongo works correctly.
        Test Case
            button push: Yes
            find_result: True
            request_module_id: False
            before status: None
        Expected Results
            status: --- -> True
        """

        self._url = reverse('finish_playback_mongo', kwargs={'course_id': unicode(self.course.id)})

        _module_list = PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=False)
        _module_list['block_id'] = 999999
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[_module_list])

        before = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        response = self.client.post(self._url, data={'data': 'Yes',
                                                     'module_id': self.module_x11_video1.location.block_id})

        search_result = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))
        for mid in search_result[0]['module_list']:
            if not mid['block_id'] == self.module_x11_video1.location.block_id:
                after = mid

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before[0]['module_list'][0]['status'], False)
        self.assertEqual(after['status'], False)

    def test_finish_playback_mongo_from_none_to_true_when_not_find_result(self):
        """
        Tests that verify that the finish_playback_mongo works correctly.
        Test Case
            button push: Yes
            find_result: False
        Expected Results
            status: --- -> True
        """

        self._url = reverse('finish_playback_mongo', kwargs={'course_id': unicode(self.course.id)})

        before = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        response = self.client.post(self._url, data={'data': 'Yes',
                                                     'module_id': self.module_x11_video1.location.block_id})

        after = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(len(before), len(after))
        self.assertEqual(before, [])
        self.assertEqual(after[0]['module_list'][0]['status'], True)

    def test_finish_playback_mongo_from_none_to_false(self):
        """
        Tests that verify that the finish_playback_mongo works correctly.
        Test Case
            button push: No
            find_result: True
            request_module_id: False
        Expected Results
            status: --- -> False
        """

        self._url = reverse('finish_playback_mongo', kwargs={'course_id': unicode(self.course.id)})

        _module_list = PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=True)
        _module_list['block_id'] = 999999
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[_module_list])

        before = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        response = self.client.post(self._url, data={'data': 'No',
                                                     'module_id': self.module_x11_video1.location.block_id})

        search_result = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))
        for mid in search_result[0]['module_list']:
            if not mid['block_id'] == self.module_x11_video1.location.block_id:
                after = mid

        self.assertEqual(response.status_code, 200)
        self.assertEqual(before[0]['module_list'][0]['status'], True)
        self.assertEqual(mid['status'], False)

    def test_finish_playback_mongo_from_none_to_false_when_not_find_result(self):
        """
        Tests that verify that the finish_playback_mongo works correctly.
        Test Case
            button push: No
            find_result: False
        Expected Results
            status: --- -> False
        """

        self._url = reverse('finish_playback_mongo', kwargs={'course_id': unicode(self.course.id)})

        before = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        response = self.client.post(self._url, data={'data': 'No',
                                                     'module_id': self.module_x11_video1.location.block_id})

        after = PlaybackFinishStore().find_record(self.user.id, unicode(self.course.id))

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(len(before), len(after))
        self.assertEqual(before, [])
        self.assertEqual(after[0]['module_list'][0]['status'], False)

    def test_error_response(self):
        self._url = reverse('finish_playback_mongo', kwargs={'course_id': unicode(self.course.id)})
        response = self.client.post(self._url, data={'data': 'hoge',
                                                     'module_id': self.module_x11_video1.location.block_id})
        self.assertEqual(response.status_code, 400)

    def test_search_playback_mongo_when_false_module_status_managed(self):
        self._url = reverse('search_playback_mongo', kwargs={'course_id': unicode(self.course.id)})
        # arrange
        self.course.is_status_managed = True
        self.update_course(self.course, self.user.id)

        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=False)])

        response = self.client.post(self._url)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['find_result'], True)

    def test_search_playback_mongo_when_find_result(self):
        self._url = reverse('search_playback_mongo', kwargs={'course_id': unicode(self.course.id)})
        # arrange
        self.course.is_status_managed = True
        self.update_course(self.course, self.user.id)

        _module_list = PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=False)
        _module_list['block_id'] = 999999
        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[_module_list])

        response = self.client.post(self._url, data={'block_id': self.module_x11_video1.location.block_id})
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['find_result'], False)

    def test_search_playback_mongo_when_not_find_result(self):
        self._url = reverse('search_playback_mongo', kwargs={'course_id': unicode(self.course.id)})
        # arrange
        self.course.is_status_managed = True
        self.update_course(self.course, self.user.id)

        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=False)])

        response = self.client.post(self._url, data={'block_id': self.module_x11_video1.location.block_id})
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['find_result'], False)

    def test_search_playback_mongo_when_no_course_status_managed(self):
        self._url = reverse('search_playback_mongo', kwargs={'course_id': unicode(self.course.id)})
        # arrange
        self.course.is_status_managed = False
        self.update_course(self.course, self.user.id)

        PlaybackFinishFactory._create(course=self.course, user=self.user, module_list=[
            PlaybackFinishFactory._create_module_param(module=self.module_x11_video1, status=True)])

        response = self.client.post(self._url)
        data = json.loads(response.content)

        self.assertEqual(data['find_result'], True)
