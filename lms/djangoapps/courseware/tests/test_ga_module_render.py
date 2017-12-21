# -*- coding: utf-8 -*-
"""
Test for lms courseware app, module render unit
"""
import ddt
import json
from nose.plugins.attrib import attr
from mock import Mock, patch

from django.test.client import RequestFactory
from capa.tests.response_xml_factory import OptionResponseXMLFactory
from courseware import module_render as render
from courseware.model_data import FieldDataCache
from courseware.tests.factories import (
    GaCourseScorerFactory,
    GaGlobalCourseCreatorFactory,
    GlobalStaffFactory,
    StudentModuleFactory,
    UserFactory,
)
from courseware.tests.test_ga_progress_restriction import ProgressRestrictionTestBase
from lms.djangoapps.lms_xblock.runtime import quote_slashes
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import ItemFactory, CourseFactory
from xmodule.x_module import XModuleDescriptor, XModule, STUDENT_VIEW, CombinedSystem


class LMSXBlockServiceBindingTestWithGaGlobalCourseCreator(ModuleStoreTestCase):
    """
    Tests that the LMS Module System (XBlock Runtime) provides an expected set of services.
    """

    def setUp(self):
        """
        Set up the user and other fields that will be used to instantiate the runtime.
        """
        super(LMSXBlockServiceBindingTestWithGaGlobalCourseCreator, self).setUp()
        self.course = CourseFactory.create()
        self._set_up_user()
        self.student_data = Mock()
        self.track_function = Mock()
        self.xqueue_callback_url_prefix = Mock()
        self.request_token = Mock()

    def _set_up_user(self):
        self.user = GaGlobalCourseCreatorFactory()

    def _assert_runtime(self, runtime):
        # pylint: disable=no-member
        self.assertFalse(runtime.user_is_staff)
        self.assertFalse(runtime.user_is_admin)
        self.assertFalse(runtime.user_is_beta_tester)
        self.assertEqual(runtime.days_early_for_beta, 5)

    def test_is_staff(self):
        """
        Tests that the beta tester fields are set on LMS runtime.
        """
        descriptor = ItemFactory(category="pure", parent=self.course)
        descriptor.days_early_for_beta = 5
        runtime, _ = render.get_module_system_for_user(
            self.user,
            self.student_data,
            descriptor,
            self.course.id,
            self.track_function,
            self.xqueue_callback_url_prefix,
            self.request_token,
            course=self.course
        )

        self._assert_runtime(runtime)


class LMSXBlockServiceBindingTestWithGaCourseScorer(LMSXBlockServiceBindingTestWithGaGlobalCourseCreator):
    """
    Tests that the LMS Module System (XBlock Runtime) provides an expected set of services.
    """

    def _set_up_user(self):
        self.user = GaCourseScorerFactory(course_key=self.course.id)

    def _assert_runtime(self, runtime):
        self.assertTrue(runtime.user_is_staff)
        self.assertFalse(runtime.user_is_admin)
        self.assertFalse(runtime.user_is_beta_tester)
        self.assertEqual(runtime.days_early_for_beta, 5)


class MongoViewInStudioWithRoleMixIn(ModuleStoreTestCase):
    """Test the 'View in Studio' link visibility in a mongo backed course."""

    def _set_up_user(self):
        """ Set up the user and request that will be used. """
        raise NotImplementedError

    def _get_module(self, course_id, descriptor, location):
        """
        Get the module from the course from which to pattern match (or not) the 'View in Studio' buttons
        """
        field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            course_id,
            self.user,
            descriptor
        )

        return render.get_module(
            self.user,
            self.request,
            location,
            field_data_cache,
        )

    def setup_mongo_course(self, course_edit_method='Studio'):
        """ Create a mongo backed course. """
        self.course = CourseFactory.create(
            course_edit_method=course_edit_method
        )

        descriptor = ItemFactory.create(
            category='vertical',
            parent_location=self.course.location,
        )

        child_descriptor = ItemFactory.create(
            category='vertical',
            parent_location=descriptor.location
        )

        self._set_up_user()
        self.request = RequestFactory().get('/')
        self.request.user = self.user
        self.request.session = {}

        self.module = self._get_module(self.course.id, descriptor, descriptor.location)

        # pylint: disable=attribute-defined-outside-init
        self.child_module = self._get_module(self.course.id, child_descriptor, child_descriptor.location)


class MongoViewInStudioTestWithGaGlobalCourseCreator(MongoViewInStudioWithRoleMixIn):
    """Test the 'View in Studio' link visibility in a mongo backed course."""

    def _set_up_user(self):
        """ Set up the user and request that will be used. """
        self.user = GaGlobalCourseCreatorFactory()

    def test_view_in_studio_link_studio_course(self):
        """Regular Studio courses should see 'View in Studio' links."""
        self.setup_mongo_course()
        result_fragment = self.module.render(STUDENT_VIEW)
        self.assertNotIn('View Unit in Studio', result_fragment.content)

    def test_view_in_studio_link_only_in_top_level_vertical(self):
        """Regular Studio courses should not see 'View in Studio' for child verticals of verticals."""
        self.setup_mongo_course()
        # Render the parent vertical, then check that there is only a single "View Unit in Studio" link.
        result_fragment = self.module.render(STUDENT_VIEW)
        # The single "View Unit in Studio" link should appear before the first xmodule vertical definition.
        parts = result_fragment.content.split('data-block-type="vertical"')
        self.assertEqual(3, len(parts), "Did not find two vertical blocks")
        self.assertNotIn('View Unit in Studio', parts[0])
        self.assertNotIn('View Unit in Studio', parts[1])
        self.assertNotIn('View Unit in Studio', parts[2])

    def test_view_in_studio_link_xml_authored(self):
        """Courses that change 'course_edit_method' setting can hide 'View in Studio' links."""
        self.setup_mongo_course(course_edit_method='XML')
        result_fragment = self.module.render(STUDENT_VIEW)
        self.assertNotIn('View Unit in Studio', result_fragment.content)


class MongoViewInStudioTestWithGaCourseScorer(MongoViewInStudioWithRoleMixIn):
    """Test the 'View in Studio' link visibility in a mongo backed course."""

    def _set_up_user(self):
        """ Set up the user and request that will be used. """
        self.user = GaCourseScorerFactory(course_key=self.course.id)

    def test_view_in_studio_link_studio_course(self):
        """Regular Studio courses should see 'View in Studio' links."""
        self.setup_mongo_course()
        result_fragment = self.module.render(STUDENT_VIEW)
        self.assertNotIn('View Unit in Studio', result_fragment.content)

    def test_view_in_studio_link_only_in_top_level_vertical(self):
        """Regular Studio courses should not see 'View in Studio' for child verticals of verticals."""
        self.setup_mongo_course()
        # Render the parent vertical, then check that there is only a single "View Unit in Studio" link.
        result_fragment = self.module.render(STUDENT_VIEW)
        # The single "View Unit in Studio" link should appear before the first xmodule vertical definition.
        parts = result_fragment.content.split('data-block-type="vertical"')
        self.assertEqual(3, len(parts), "Did not find two vertical blocks")
        self.assertNotIn('View Unit in Studio', parts[0])
        self.assertNotIn('View Unit in Studio', parts[1])
        self.assertNotIn('View Unit in Studio', parts[2])

    def test_view_in_studio_link_xml_authored(self):
        """Courses that change 'course_edit_method' setting can hide 'View in Studio' links."""
        self.setup_mongo_course(course_edit_method='XML')
        result_fragment = self.module.render(STUDENT_VIEW)
        self.assertNotIn('View Unit in Studio', result_fragment.content)


class TestStaffDebugInfoWithRoleMixIn(ModuleStoreTestCase):
    def _set_up_user(self):
        raise NotImplementedError

    def setUp(self):
        super(TestStaffDebugInfoWithRoleMixIn, self).setUp()
        self.course = CourseFactory.create()
        self._set_up_user()
        self.request = RequestFactory().get('/')
        self.request.user = self.user
        self.request.session = {}

        problem_xml = OptionResponseXMLFactory().build_xml(
            question_text='The correct answer is Correct',
            num_inputs=2,
            weight=2,
            options=['Correct', 'Incorrect'],
            correct_option='Correct'
        )
        self.descriptor = ItemFactory.create(
            category='problem',
            data=problem_xml,
            display_name='Option Response Problem'
        )

        self.location = self.descriptor.location
        self.field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            self.course.id,
            self.user,
            self.descriptor
        )


@patch.dict('django.conf.settings.FEATURES', {'DISPLAY_DEBUG_INFO_TO_STAFF': True, 'DISPLAY_HISTOGRAMS_TO_STAFF': True})
@patch('courseware.module_render.has_access', Mock(return_value=True, autospec=True))
class TestStaffDebugInfoWithGaGlobalCourseCreator(TestStaffDebugInfoWithRoleMixIn):
    """Tests to verify that Staff Debug Info panel and histograms are displayed to staff."""

    def _set_up_user(self):
        self.user = GaGlobalCourseCreatorFactory.create()

    @patch.dict('django.conf.settings.FEATURES', {'DISPLAY_DEBUG_INFO_TO_STAFF': False})
    def test_staff_debug_info_disabled(self):
        module = render.get_module(
            self.user,
            self.request,
            self.location,
            self.field_data_cache,
        )
        result_fragment = module.render(STUDENT_VIEW)
        self.assertNotIn('Staff Debug', result_fragment.content)

    def test_staff_debug_info_enabled(self):
        module = render.get_module(
            self.user,
            self.request,
            self.location,
            self.field_data_cache,
        )
        result_fragment = module.render(STUDENT_VIEW)
        self.assertNotIn('Staff Debug', result_fragment.content)

    @patch.dict('django.conf.settings.FEATURES', {'DISPLAY_HISTOGRAMS_TO_STAFF': False})
    def test_histogram_disabled(self):
        module = render.get_module(
            self.user,
            self.request,
            self.location,
            self.field_data_cache,
        )
        result_fragment = module.render(STUDENT_VIEW)
        self.assertNotIn('histogram', result_fragment.content)
        self.assertNotIn('Staff Debug', result_fragment.content)

    def test_histogram_enabled_for_unscored_xmodules(self):
        """Histograms should not display for xmodules which are not scored."""

        html_descriptor = ItemFactory.create(
            category='html',
            data='Here are some course details.'
        )
        field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            self.course.id,
            self.user,
            self.descriptor
        )
        with patch('openedx.core.lib.xblock_utils.grade_histogram') as mock_grade_histogram:
            mock_grade_histogram.return_value = []
            module = render.get_module(
                self.user,
                self.request,
                html_descriptor.location,
                field_data_cache,
            )
            module.render(STUDENT_VIEW)
            self.assertFalse(mock_grade_histogram.called)

    def test_histogram_enabled_for_scored_xmodules(self):
        """Histograms should display for xmodules which are scored."""

        StudentModuleFactory.create(
            course_id=self.course.id,
            module_state_key=self.location,
            student=UserFactory(),
            grade=1,
            max_grade=1,
            state="{}",
        )
        with patch('openedx.core.lib.xblock_utils.grade_histogram') as mock_grade_histogram:
            mock_grade_histogram.return_value = []
            module = render.get_module(
                self.user,
                self.request,
                self.location,
                self.field_data_cache,
            )
            result_fragment = module.render(STUDENT_VIEW)
            self.assertFalse(mock_grade_histogram.called)
            self.assertNotIn('Staff Debug', result_fragment.content)


@patch.dict('django.conf.settings.FEATURES', {'DISPLAY_DEBUG_INFO_TO_STAFF': True, 'DISPLAY_HISTOGRAMS_TO_STAFF': True})
@patch('courseware.module_render.has_access', Mock(return_value=True, autospec=True))
class TestStaffDebugInfoWithGaCourseScorer(TestStaffDebugInfoWithRoleMixIn):
    """Tests to verify that Staff Debug Info panel and histograms are displayed to staff."""

    def _set_up_user(self):
        self.user = GaCourseScorerFactory.create(course_key=self.course.id)

    @patch.dict('django.conf.settings.FEATURES', {'DISPLAY_DEBUG_INFO_TO_STAFF': False})
    def test_staff_debug_info_disabled(self):
        module = render.get_module(
            self.user,
            self.request,
            self.location,
            self.field_data_cache,
        )
        result_fragment = module.render(STUDENT_VIEW)
        self.assertNotIn('Staff Debug', result_fragment.content)

    def test_staff_debug_info_enabled(self):
        module = render.get_module(
            self.user,
            self.request,
            self.location,
            self.field_data_cache,
        )
        result_fragment = module.render(STUDENT_VIEW)
        self.assertIn('Staff Debug', result_fragment.content)

    @patch.dict('django.conf.settings.FEATURES', {'DISPLAY_HISTOGRAMS_TO_STAFF': False})
    def test_histogram_disabled(self):
        module = render.get_module(
            self.user,
            self.request,
            self.location,
            self.field_data_cache,
        )
        result_fragment = module.render(STUDENT_VIEW)
        self.assertNotIn('histogram', result_fragment.content)
        self.assertIn('Staff Debug', result_fragment.content)

    def test_histogram_enabled_for_unscored_xmodules(self):
        """Histograms should not display for xmodules which are not scored."""

        html_descriptor = ItemFactory.create(
            category='html',
            data='Here are some course details.'
        )
        field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
            self.course.id,
            self.user,
            self.descriptor
        )
        with patch('openedx.core.lib.xblock_utils.grade_histogram') as mock_grade_histogram:
            mock_grade_histogram.return_value = []
            module = render.get_module(
                self.user,
                self.request,
                html_descriptor.location,
                field_data_cache,
            )
            module.render(STUDENT_VIEW)
            self.assertFalse(mock_grade_histogram.called)

    def test_histogram_enabled_for_scored_xmodules(self):
        """Histograms should display for xmodules which are scored."""

        StudentModuleFactory.create(
            course_id=self.course.id,
            module_state_key=self.location,
            student=UserFactory(),
            grade=1,
            max_grade=1,
            state="{}",
        )
        with patch('openedx.core.lib.xblock_utils.grade_histogram') as mock_grade_histogram:
            mock_grade_histogram.return_value = []
            module = render.get_module(
                self.user,
                self.request,
                self.location,
                self.field_data_cache,
            )
            result_fragment = module.render(STUDENT_VIEW)
            self.assertTrue(mock_grade_histogram.called)
            self.assertIn('Staff Debug', result_fragment.content)


@attr('shard_1')
class TestModuleTrackingContextWithProgressRestriction(ProgressRestrictionTestBase):
    """
    Ensure correct tracking information is included in events emitted during XBlock callback handling.
    """
    def setUp(self):
        super(TestModuleTrackingContextWithProgressRestriction, self).setUp()

        self.request = RequestFactory().get('/')
        self.request.user = self.user
        self.request.session = {}

    def test_progress_restriction_info(self):
        self.set_course_optional_setting()
        content = self.submit_problem(self.problem1, {'2_1': 'Correct'})
        self.assertIn('restricted_list', content)
        self.assertIn('restricted_chapters', content)
        self.assertIn('restricted_sections', content)

    def test_progress_restriction_info_before_answer_correctly(self):
        self.set_course_optional_setting()
        content = self.submit_problem(self.problem1, {'2_2': 'Incorrect'})
        content_json = json.loads(content)
        self.assertEqual(content_json['restricted_list'], [3])
        self.assertEqual(content_json['restricted_chapters'], [1, 2])
        self.assertEqual(content_json['restricted_sections'], {u'0': [2], u'1': [1, 2], u'2': [1, 2]})

    def test_progress_restriction_info_after_answer_correctly(self):
        self.set_course_optional_setting()
        self.submit_problem(self.problem1, {'2_1': 'Correct'})
        self.submit_problem(self.problem3, {'2_1': 'Correct'})
        self.submit_problem(self.problem4, {'2_1': 'Correct'})
        content = self.submit_problem(self.problem1, {'2_1': 'Correct'})
        content_json = json.loads(content)
        self.assertEqual(content_json['restricted_list'], [])
        self.assertEqual(content_json['restricted_chapters'], [])
        self.assertEqual(content_json['restricted_sections'], {u'0': [], u'1': [], u'2': []})
