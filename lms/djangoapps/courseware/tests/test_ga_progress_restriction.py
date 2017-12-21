import ddt
from capa.tests.response_xml_factory import OptionResponseXMLFactory
from courseware.ga_progress_restriction import ProgressRestriction
from courseware.model_data import FieldDataCache
from courseware.module_render import get_module_for_descriptor
from courseware.tests.helpers import LoginEnrollmentTestCase
from django.core.urlresolvers import reverse
from django.test.client import RequestFactory
from lms.djangoapps.lms_xblock.runtime import quote_slashes
from nose.plugins.attrib import attr
from openedx.core.djangoapps.ga_optional.models import CourseOptionalConfiguration
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


@attr('shard_1')
@ddt.ddt
class ProgressRestrictionTestBase(ModuleStoreTestCase, LoginEnrollmentTestCase):
    """Test methods related to progress restriction."""

    def setUp(self):
        super(ProgressRestrictionTestBase, self).setUp()

        # self.course = CourseFactory.create(start=timezone.now() - timedelta(days=10))
        self.course = CourseFactory.create()
        self.setup_user()
        self.enroll(self.course)
        self.factory = RequestFactory()

        self.vertical_number = dict()
        self.chapters = []
        self.chapter_ids = []
        self.chapter_location_names = []
        self.sections = []
        self.section_location_names = []
        self.verticals = []

        self.setup_course()

    def set_course_optional_setting(self):
        self.course_optional_configuration = CourseOptionalConfiguration(
            id=1,
            change_date="2017-11-06 16:02:13",
            enabled=True,
            key='progress-restriction-settings',
            course_key=self.course.id,
            changed_by_id=self.user.id
        )
        self.course_optional_configuration.save()

    def setup_course(self):
        vertical_metadata_with_restriction = {
            'graded': True,
            'format': 'Homework',
            'due': '2030-12-25T00:00',
            'progress_restriction': {
                'type': 'Correct Answer Rate',
                'passing_mark': 50,
            }
        }
        vertical_metadata_without_restriction_01 = {
            'graded': True,
            'format': 'Homework',
            'due': '2030-12-25T00:00',
            'progress_restriction': {
                'type': 'No Restriction',
            }
        }
        vertical_metadata_without_restriction_02 = {
            'graded': True,
            'format': 'Homework',
            'due': '2030-12-25T00:00',
        }

        with modulestore().default_store(ModuleStoreEnum.Type.mongo):
            for ch_idx in range(3):
                self.chapters.append(ItemFactory(parent=self.course, category='chapter', graded=True))
                self.chapter_ids.append(ch_idx)
                self.chapter_location_names.append(self.chapters[ch_idx].location.name)

                self.sections.append([])
                for sc_idx in range(2):
                    self.sections[ch_idx].append(ItemFactory(parent=self.chapters[ch_idx], category='sequential'))
                    self.section_location_names.append(self.sections[ch_idx][sc_idx].location.name)

                    self.verticals.append(
                        ItemFactory(parent=self.sections[ch_idx][sc_idx],
                                    category='vertical',
                                    metadata=vertical_metadata_with_restriction)
                    )
                    self.verticals.append(
                        ItemFactory(parent=self.sections[ch_idx][sc_idx],
                                    category='vertical',
                                    metadata=vertical_metadata_without_restriction_01)
                    )
                    self.verticals.append(
                        ItemFactory(parent=self.sections[ch_idx][sc_idx],
                                    category='vertical',
                                    metadata=vertical_metadata_with_restriction)
                    )
                    self.verticals.append(
                        ItemFactory(parent=self.sections[ch_idx][sc_idx],
                                    category='vertical',
                                    metadata=vertical_metadata_without_restriction_02)
                    )

            self.prob_xml = OptionResponseXMLFactory().build_xml(
                question_text='The correct answer is Correct',
                num_inputs=1,
                weight=1,
                options=['Correct', 'Incorrect'],
                correct_option='Correct'
            )

            # chapter 1 / section 1 / vertical 3
            self.problem1 = ItemFactory.create(
                parent_location=self.verticals[2].location,
                category='problem',
                data=self.prob_xml,
                display_name='p1'
            )

            self.problem2 = ItemFactory.create(
                parent_location=self.verticals[2].location,
                category='problem',
                data=self.prob_xml,
                display_name='p2'
            )

            # chapter 1 / section 2 / vertical 1
            self.problem3 = ItemFactory.create(
                parent_location=self.verticals[4].location,
                category='problem',
                data=self.prob_xml,
                display_name='p3'
            )

            # chapter 2 / section 1 / vertical 1
            self.problem4 = ItemFactory.create(
                parent_location=self.verticals[8].location,
                category='problem',
                data=self.prob_xml,
                display_name='p4'
            )

            self.course = modulestore().get_course(self.course.id, depth=5)

    def submit_problem(self, problem, responses):
        answer_key_prefix = 'input_{}_'.format(problem.location.html_id())

        # format the response dictionary to be sent in the post request by adding the above prefix to each key
        response_dict = {(answer_key_prefix + k): v for k, v in responses.items()}

        resp = self.client.post(
            reverse(
                'xblock_handler',
                    kwargs={
                        'course_id': self.course.id.to_deprecated_string(),
                        'usage_id': quote_slashes(problem.location.to_deprecated_string()),
                        'handler': 'xmodule_handler',
                        'suffix': 'problem_check',
                    }
            ),
            response_dict
        )

        self.assertEqual(resp.status_code, 200)

        return resp.content

    def get_progress_restriction_obj(self):
        fake_request = self.factory.get(
            reverse('courseware', kwargs={'course_id': unicode(self.course.id)})
        )

        with modulestore().bulk_operations(self.course.id):
            field_data_cache = FieldDataCache.cache_for_descriptor_descendents(
                self.course.id, self.user, self.course, depth=5
            )
            course_module = get_module_for_descriptor(
                self.user,
                fake_request,
                self.course,
                field_data_cache,
                self.course.id,
                course=self.course
            )
            progress_restriction = ProgressRestriction(self.course.id, self.user, course_module)

        return progress_restriction


@attr('shard_1')
@ddt.ddt
class ProgressRestrictionTest(ProgressRestrictionTestBase):
    """Test methods related to progress restriction."""

    def setUp(self):
        super(ProgressRestrictionTest, self).setUp()

    def test_get_restricted_list_in_section_before_answer_correctly(self):
        self.set_course_optional_setting()

        self.submit_problem(self.problem1, {'2_1': 'Correct'})

        progress_restriction = self.get_progress_restriction_obj()

        self.assertEqual(
            progress_restriction.get_restricted_list_in_section(self.section_location_names[1]),
            [1, 2, 3]
        )

    def test_get_restricted_list_in_section_after_answer_correctly(self):
        self.set_course_optional_setting()

        self.submit_problem(self.problem1, {'2_1': 'Correct'})
        self.submit_problem(self.problem3, {'2_1': 'Correct'})

        progress_restriction = self.get_progress_restriction_obj()

        self.assertEqual(
            progress_restriction.get_restricted_list_in_section(self.section_location_names[1]),
            []
        )

    def test_get_restricted_list_in_same_section_before_answer_correctly(self):
        self.set_course_optional_setting()

        self.submit_problem(self.problem1, {'2_1': 'Correct'})

        progress_restriction = self.get_progress_restriction_obj()

        self.assertEqual(
            progress_restriction.get_restricted_list_in_same_section(unicode(self.verticals[4].location.name)),
            [1, 2, 3]
        )

    def test_get_restricted_list_in_same_section_after_answer_correctly(self):
        self.set_course_optional_setting()

        self.submit_problem(self.problem1, {'2_1': 'Correct'})
        self.submit_problem(self.problem3, {'2_1': 'Correct'})

        progress_restriction = self.get_progress_restriction_obj()

        self.assertEqual(
            progress_restriction.get_restricted_list_in_same_section(unicode(self.verticals[4].location.name)),
            []
        )

    def test_get_restricted_chapters_before_answer(self):
        self.set_course_optional_setting()

        progress_restriction = self.get_progress_restriction_obj()

        self.assertEqual(progress_restriction.get_restricted_chapters(), [self.chapter_ids[1],
                                                                          self.chapter_ids[2]])

    def test_get_restricted_chapters_after_answer(self):
        self.set_course_optional_setting()

        self.submit_problem(self.problem1, {'2_1': 'Correct'})
        self.submit_problem(self.problem3, {'2_1': 'Correct'})

        progress_restriction = self.get_progress_restriction_obj()

        self.assertEqual(progress_restriction.get_restricted_chapters(), [self.chapter_ids[2]])

    def test_get_restricted_sections_before_answer(self):
        self.set_course_optional_setting()

        progress_restriction = self.get_progress_restriction_obj()

        restricted_sections = progress_restriction.get_restricted_sections()

        self.assertEqual(
            restricted_sections[self.chapter_ids[0]],
            [2]
        )
        self.assertEqual(
            restricted_sections[self.chapter_ids[1]],
            [1, 2]
        )
        self.assertEqual(
            restricted_sections[self.chapter_ids[2]],
            [1, 2]
        )

    def test_get_restricted_sections_after_answer(self):
        self.set_course_optional_setting()

        self.submit_problem(self.problem1, {'2_1': 'Correct'})
        self.submit_problem(self.problem3, {'2_1': 'Correct'})
        self.submit_problem(self.problem4, {'2_1': 'Correct'})

        progress_restriction = self.get_progress_restriction_obj()
        restricted_sections = progress_restriction.get_restricted_sections()

        self.assertEqual(
            restricted_sections[self.chapter_ids[0]],
            []
        )
        self.assertEqual(
            restricted_sections[self.chapter_ids[1]],
            []
        )
        self.assertEqual(
            restricted_sections[self.chapter_ids[2]],
            []
        )

    @ddt.data(
        (0, False),
        (1, True),
        (2, True),
    )
    @ddt.unpack
    def test_is_restricted_chapter(self, chapter_idx, is_restricted):
        self.set_course_optional_setting()

        chapter = self.chapter_location_names[chapter_idx]
        progress_restriction = self.get_progress_restriction_obj()
        self.assertEqual(progress_restriction.is_restricted_chapter(chapter), is_restricted)

    @ddt.data(
        (0, False),
        (1, True),
        (2, True),
        (3, True),
        (4, True),
        (5, True),
    )
    @ddt.unpack
    def test_is_restricted_section(self, section_idx, is_restricted):
        self.set_course_optional_setting()

        section = self.section_location_names[section_idx]
        progress_restriction = self.get_progress_restriction_obj()
        self.assertEqual(progress_restriction.is_restricted_section(section), is_restricted)
