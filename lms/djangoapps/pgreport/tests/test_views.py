from django.test import TestCase
from mock import MagicMock, patch, ANY
from pgreport.views import (
    ProgressReportBase, ProblemReport, SubmissionReport, OpenAssessmentReport)
from django.test.utils import override_settings
from django.core.urlresolvers import reverse

from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from capa.tests.response_xml_factory import OptionResponseXMLFactory

from student.tests.factories import (
    UserFactory, UserStandingFactory, CourseEnrollmentFactory)
from courseware.tests.factories import (
    InstructorFactory, StaffFactory, StudentModuleFactory)
from student.models import UserStanding
from courseware.tests.factories import StaffFactory, InstructorFactory

from courseware.courses import get_course
from capa.correctmap import CorrectMap

import json

from openassessment.assessment.models import Assessment, AssessmentPart
from openassessment.assessment.serializers import rubric_from_dict
from submissions import api as sub_api
from openassessment.assessment.api import peer as peer_api
from openassessment.workflow import api as workflow_api


class ProgressReportBaseTestCase(TestCase):
    """ Test ProgressReportBase"""

    def setUp(self):
        self.course_id = 'course-v1:org+cn+run'
        self.progress = ProgressReportBase(self.course_id)

    def tearDown(self):
        pass

    def test_get_course_id(self):
        course_id = self.progress.get_course_id(self.course_id)
        self.assertIsInstance(course_id, CourseKey)

    def test_get_course_id_by_course_key(self):
        course_key = CourseKey.from_string(self.course_id)
        course_id = self.progress.get_course_id(course_key)
        self.assertIsInstance(course_id, CourseKey)

    def test_get_course_location(self):
        course_location = self.progress.get_course_location(self.course_id)
        self.assertIsInstance(course_location, CourseLocator)

    def test_get_course_location_by_course_locator(self):
        course_locator = CourseLocator.from_string(self.course_id)
        course_location = self.progress.get_course_location(course_locator)
        self.assertIsInstance(course_location, CourseLocator)

    @patch('pgreport.views.modulestore')
    def test_get_display_name(self, mod_mock):
        name_mock = MagicMock()
        name_mock.display_name_with_default = "test_name"
        name_mock.scope_ids.usage_id = "item_id"
        mod_mock.return_value.get_items.return_value = [name_mock]

        name = self.progress.get_display_name(
            self.course_id, "item_id")

        mod_mock.assert_called_with()
        mod_mock().get_items.assert_called_with(
            self.course_id, qualifiers={'category': "openassessment"})
        self.assertEquals(name, "test_name")


class ProblemReportTestCase(ModuleStoreTestCase):
    """ Test ProblemReport"""
    COURSE_NAME = "test_pgreport"
    COURSE_NUM = 3

    def setUp(self):
        super(ProblemReportTestCase, self).setUp()

        self.course = CourseFactory.create(
            display_name=self.COURSE_NAME,
        )

        self.course.raw_grader = [{
            'drop_count': 0,
            'min_count': 1,
            'short_label': 'Final',
            'type': 'Final Exam',
            'weight': 1.0
        }]
        self.course.grade_cutoffs = {'Pass': 0.1}
        self.students = [
            UserFactory.create(username='student1'),
            UserFactory.create(username='student2'),
            UserFactory.create(username='student3'),
            UserFactory.create(username='student4'),
            UserFactory.create(username='student5'),
            StaffFactory.create(username='staff1', course_key=self.course.id),
            InstructorFactory.create(username='instructor1', course_key=self.course.id),
        ]

        UserStandingFactory.create(
            user=self.students[4],
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=self.students[6]
        )

        for user in self.students:
            CourseEnrollmentFactory.create(user=user, course_id=self.course.id)

        self.pgreport = ProblemReport(self.course.id)

        self.chapter = ItemFactory.create(
            parent_location=self.course.location,
            category="chapter",
            display_name="Week 1"
        )
        self.chapter.save()
        self.section = ItemFactory.create(
            parent_location=self.chapter.location,
            category="sequential",
            display_name="Lesson 1"
        )
        self.section.save()
        self.vertical = ItemFactory.create(
            parent_location=self.section.location,
            category="vertical",
            display_name="Unit1"
        )
        self.vertical.save()
        self.html = ItemFactory.create(
            parent_location=self.vertical.location,
            category="html",
            data={'data': "<html>foobar</html>"}
        )
        self.html.save()

        self.problem_xml = OptionResponseXMLFactory().build_xml(
            question_text='The correct answer is Correct',
            num_inputs=2,
            weight=2,
            options=['Correct', 'Incorrect'],
            correct_option='Correct'
        )

        self.problems = []
        for num in xrange(1, 4):
            self.problems.append(ItemFactory.create(
                parent_location=self.vertical.location,
                category='problem',
                display_name='problem_' + str(num),
                metadata={'graded': True, 'format': 'Final Exam'},
                data=self.problem_xml
            ))
            self.problems[num - 1].save()

        for problem in self.problems:
            problem.correct_map = {
                unicode(problem.location) + "_2_1": {
                    "hint": "",
                    "hintmode": "",
                    "correctness": "correct",
                    "npoints": "",
                    "msg": "",
                    "queuestate": ""
                },
                unicode(problem.location) + "_2_2": {
                    "hint": "",
                    "hintmode": "",
                    "correctness": "incorrect",
                    "npoints": "",
                    "msg": "",
                    "queuestate": ""
                }
            }

            problem.student_answers = {
                unicode(problem.location) + "_2_1": "Correct",
                unicode(problem.location) + "_2_2": "Incorrect"
            }

            problem.input_state = {
                unicode(problem.location) + "_2_1": {},
                unicode(problem.location) + "_2_2": {}
            }

        self.course.save()

        patcher = patch('pgreport.views.logging')
        self.log_mock = patcher.start()
        self.addCleanup(patcher.stop)

        for user in self.students:
            for problem in self.problems:
                StudentModuleFactory.create(
                    grade=1,
                    max_grade=1,
                    student=user,
                    course_id=self.course.id,
                    module_type="problem",
                    module_state_key=problem.location,
                    state=json.dumps({'attempts': 1, 'done': True})
                )

        self.course_structure = [
            {
                'category': self.chapter.category,
                'indent': 0,
                'parent': [],
                'has_children': True,
                'module_size': 0,
                'display_name': self.chapter.display_name,
                'usage_id': unicode(self.chapter.location)
            },
            {
                'category': self.section.category,
                'indent': 1,
                'parent': [unicode(self.chapter.location)],
                'has_children': True,
                'module_size': 0,
                'display_name': self.section.display_name,
                'usage_id': unicode(self.section.location)
            },
            {
                'category': self.vertical.category,
                'indent': 2,
                'parent': [
                    unicode(self.chapter.location),
                    unicode(self.section.location)
                ],
                'has_children': True,
                'module_size': 0,
                'display_name': self.vertical.display_name,
                'usage_id': unicode(self.vertical.location)
            },
            {
                'category': self.problems[0].category,
                'indent': 3,
                'parent': [
                    unicode(self.chapter.location),
                    unicode(self.section.location),
                    unicode(self.vertical.location)
                ],
                'has_children': False,
                'module_size': 1,
                'display_name': self.problems[0].display_name,
                'usage_id': unicode(self.problems[0].location)
            },
            {
                'category': self.problems[1].category,
                'indent': 3,
                'parent': [
                    unicode(self.chapter.location),
                    unicode(self.section.location),
                    unicode(self.vertical.location)
                ],
                'has_children': False,
                'module_size': 1,
                'display_name': self.problems[1].display_name,
                'usage_id': unicode(self.problems[1].location)
            },
            {
                'category': self.problems[2].category,
                'indent': 3,
                'parent': [
                    unicode(self.chapter.location),
                    unicode(self.section.location),
                    unicode(self.vertical.location)
                ],
                'has_children': False,
                'module_size': 1,
                'display_name': self.problems[2].display_name,
                'usage_id': unicode(self.problems[2].location)
            },
        ]

    def tearDown(self):
        pass

    def test_get_active_students(self):
        counts, actives = self.pgreport.get_active_students()
        self.assertEquals(counts, 7)
        self.assertEquals(actives, 6)

    @patch('pgreport.views.ProblemReport._get_children_module')
    def test_get_course_structure(self, getcm_mock):
        course = get_course(self.course.id)
        self.pgreport.get_course_structure()
        getcm_mock.assert_called_once_with(course)

    def test_get_children_module(self):
        course = get_course(self.course.id)
        self.pgreport._get_children_module(course)
        self.assertEquals(self.pgreport.location_list, self.course_structure)

    @patch('pgreport.views.ProblemReport._get_student_answers_data')
    @patch('pgreport.views.ProblemReport._get_correctmap_data')
    def test_get_problem_data(self, gc_mock, gsa_mock):
        problem_data = self.pgreport.get_problem_data()
        self.assertEquals(
            problem_data, {
                unicode(self.problems[0].location): {
                    'counts': 7,
                    'correct_maps': gc_mock.return_value,
                    'attempts': 7,
                    'student_answers': gsa_mock.return_value,
                },
                unicode(self.problems[1].location): {
                    'counts': 7,
                    'correct_maps': gc_mock.return_value,
                    'attempts': 7,
                    'student_answers': gsa_mock.return_value,
                },
                unicode(self.problems[2].location): {
                    'counts': 7,
                    'correct_maps': gc_mock.return_value,
                    'attempts': 7,
                    'student_answers': gsa_mock.return_value,
                }
            }
        )

    def test_get_correctmap_data(self):
        sum_cmap = {}
        cmap = CorrectMap()
        cmap.set(answer_id='1_2_1', correctness='correct')
        cmap.set(answer_id='1_2_2', correctness='incorrect')
        cmap.set(answer_id='1_2_3', correctness='correct')

        return_cmap = self.pgreport._get_correctmap_data(sum_cmap, cmap)
        self.assertEquals(return_cmap, {'1_2_3': 1, '1_2_2': 0, '1_2_1': 1})

        cmap.set(answer_id='1_2_3', correctness='incorrect')
        cmap.set(answer_id='1_2_4', correctness='correct')

        return_cmap = self.pgreport._get_correctmap_data(sum_cmap, cmap)
        self.assertEquals(return_cmap, {'1_2_4': 1, '1_2_3': 1, '1_2_2': 0, '1_2_1': 2})

    def test_get_student_answers_data(self):
        sum_answers = {}
        student_answers = {'1_2_1': 'abcd', '1_2_2': 'abcd', '1_2_3': 'xyz'}
        return_answers = self.pgreport._get_student_answers_data(
            sum_answers, student_answers)
        self.assertEquals(return_answers, {
            '1_2_1': {'abcd': 1}, '1_2_3': {'xyz': 1}, '1_2_2': {'abcd': 1}})

        student_answers = {'1_2_1': 'abcd', '1_2_2': 'xyz', '1_2_3': 'xyz'}
        return_answers = self.pgreport._get_student_answers_data(
            sum_answers, student_answers)
        self.assertEquals(return_answers, {
            '1_2_1': {'abcd': 2}, '1_2_3': {'xyz': 2}, '1_2_2': {'abcd': 1, 'xyz': 1}})

        student_answers = {'2_2_1': ['abc', 'def'], '2_2_2': ['xyz']}
        return_answers = self.pgreport._get_student_answers_data(
            sum_answers, student_answers)
        self.assertEquals(return_answers, {
            '1_2_1': {'abcd': 2}, '1_2_3': {'xyz': 2}, '1_2_2': {'abcd': 1, 'xyz': 1},
            '2_2_1': {'abc': 1, 'def': 1}, '2_2_2': {'xyz': 1}})

    @patch('pgreport.views.ProblemReport.get_problem_data')
    @patch('pgreport.views.ProblemReport.get_course_structure')
    def test_get_pgreport(self, getcs_mock, getpd_mock):
        getcs_mock.return_value = self.course_structure
        getpd_mock.return_value = {
            unicode(self.problems[0].location): {
                'counts': 7,
                'correct_maps': {'1_2_1': 1, '1_2_2': 3},
                'attempts': 7,
                'student_answers': {'1_2_1': {'abcd': 2}, '1_2_2': {'xyz': 1}},
            },
            unicode(self.problems[1].location): {
                'counts': 7,
                'correct_maps': {'2_2_1': 0, '2_2_2': 5},
                'attempts': 7,
                'student_answers': {'2_2_1': {'abcd': 4}, '2_2_2': {'abc': 3}},
            }
        }

        question1 = {
            'category': self.problems[0].category,
            'indent': 3,
            'parent': [
                unicode(self.chapter.location),
                unicode(self.section.location),
                unicode(self.vertical.location)
            ],
            'has_children': False,
            'module_size': 1,
            'display_name': self.problems[0].display_name,
            'usage_id': unicode(self.problems[0].location),
            'attempts': 7,
            'counts': 7,
            'module_id': '1_2_1',
            'student_answers': {'abcd': 2},
            'correct_counts': 1
        }

        question2 = {
            'category': self.problems[0].category,
            'indent': 3,
            'parent': [
                unicode(self.chapter.location),
                unicode(self.section.location),
                unicode(self.vertical.location)
            ],
            'has_children': False,
            'module_size': 1,
            'display_name': self.problems[0].display_name,
            'usage_id': unicode(self.problems[0].location),
            'attempts': 7,
            'counts': 7,
            'module_id': '1_2_2',
            'student_answers': {'xyz': 1},
            'correct_counts': 3
        }

        question3 = {
            'category': self.problems[1].category,
            'indent': 3,
            'parent': [
                unicode(self.chapter.location),
                unicode(self.section.location),
                unicode(self.vertical.location)
            ],
            'has_children': False,
            'module_size': 1,
            'display_name': self.problems[1].display_name,
            'usage_id': unicode(self.problems[1].location),
            'attempts': 7,
            'counts': 7,
            'module_id': '2_2_1',
            'student_answers': {'abcd': 4},
            'correct_counts': 0
        }
        question4 = {
            'category': self.problems[1].category,
            'indent': 3,
            'parent': [
                unicode(self.chapter.location),
                unicode(self.section.location),
                unicode(self.vertical.location)
            ],
            'has_children': False,
            'module_size': 1,
            'display_name': self.problems[1].display_name,
            'usage_id': unicode(self.problems[1].location),
            'attempts': 7,
            'counts': 7,
            'module_id': '2_2_2',
            'student_answers': {'abc': 3},
            'correct_counts': 5
        }

        courses = [c for c in self.course_structure if c['category'] != 'problem']

        result = courses + [question1, question2, question3, question4]
        return_list, cache_date, in_progress = self.pgreport.get_pgreport(force=True)
        self.assertFalse(in_progress)
        self.assertItemsEqual(return_list, result)


class OpenAssessmentReportTestCase(TestCase):
    """ Test OpenAssessmentReport """
    RUBRIC_OPTIONS = [
        {
            "order_num": 0,
            "name": u"Poor",
            "label": u"Poor",
            "points": 0,
        },
        {
            "order_num": 1,
            "name": u"Good",
            "label": u"Good",
            "points": 1,
        },
        {
            "order_num": 2,
            "name": u"Excellent",
            "label": u"Excellent",
            "points": 2,
        },
    ]
    RUBRIC = {
        'criteria': [
            {
                "order_num": 0,
                "name": u"Content",
                "label": u"Content",
                "prompt": u"Content",
                "options": RUBRIC_OPTIONS
            },
            {
                "order_num": 1,
                "name": u"Ideas",
                "label": u"Ideas",
                "prompt": u"Ideas",
                "options": RUBRIC_OPTIONS
            }
        ]
    }

    def setUp(self):
        part_data = [
            {
                "selected": {'Content': 'Poor', 'Ideas': 'Good'},
                "feedback": {'Content': 'Good feedback'},
            },
            {
                "selected": {'Content': 'Excellent', 'Ideas': 'Good'},
                "feedback": {
                    'Content': 'Excellent feedback',
                    'Ideas': 'Poor feedback'
                },
            },
        ]

        rubric = rubric_from_dict(self.RUBRIC)
        assessment = Assessment.create(rubric, "Scorer", "block@openassessment@999", "PE")
        AssessmentPart.create_from_option_names(
            assessment, part_data[0]["selected"],
            feedback=part_data[0]["feedback"]
        )
        AssessmentPart.create_from_option_names(
            assessment, part_data[1]["selected"],
            feedback=part_data[1]["feedback"]
        )
        self.oa = OpenAssessmentReport('course-v1:org+cn+run')

    def tearDown(self):
        pass

    @patch(
        'pgreport.views.ProgressReportBase.get_display_name',
        return_value="display_name")
    @patch('pgreport.views.PeerWorkflow')
    def test_get_pgreport(self, pw_mock, gdn_mock):
        mock = MagicMock()
        mock.item_id = "item_id"
        mock.submission_uuid = "block@openassessment@999"
        pw_mock.objects.filter.return_value = [mock]
        scores, cache_date, in_progress = self.oa.get_pgreport(force=True)
        self.assertFalse(in_progress)
        self.assertEquals(scores, {
            "item_id": {
                'display_name': 'display_name',
                'rubrics': {
                    u'Content': {
                        u'Poor': [1, 0],
                        u'Good': [0, 1],
                        u'Excellent': [1, 2],
                    },
                    u'Ideas': {
                        u'Poor': [0, 0],
                        u'Good': [2, 1],
                        u'Excellent': [0, 2],
                    }
                }
            }
        })


class SubmissionReportTestCase(TestCase):
    """Test SubmissionReport"""
    course_id = 'course-v1:org+cn+run'
    STUDENT_ITEM = dict(
        student_id="Tim",
        course_id=course_id,
        item_id="block@openassessment@999",
        item_type="Peer_Submission",
    )
    STEPS = ['peer', 'self']

    def setUp(self):
        self._create_student_and_submission(
            'Testuser1', 'Test Answer', "block@openassessment@999", 5, 8)
        self._create_student_and_submission(
            'Testuser2', 'Test Answer', "block@openassessment@999", 8, 8)
        self._create_student_and_submission(
            'Testuser3', 'Test Answer', "block@openassessment@000", 25, 50)
        self.submission = SubmissionReport(self.course_id)

    def tearDown(self):
        pass

    def _create_student_and_submission(self, student, answer, item_id,
                                       earned, possible, date=None):

        new_student_item = self.STUDENT_ITEM.copy()
        new_student_item["student_id"] = student
        new_student_item["item_id"] = item_id

        submission = sub_api.create_submission(new_student_item, answer, date)
        peer_api.on_start(submission["uuid"])
        workflow_api.create_workflow(submission["uuid"], self.STEPS)
        sub_api.set_score(submission["uuid"], earned, possible)

        return submission, new_student_item

    @patch(
        'pgreport.views.ProgressReportBase.get_display_name',
        return_value="display_name")
    def test_get_pgreport(self, gdn_mock):
        scores, cache_date, in_progress = self.submission.get_pgreport(force=True)
        self.assertFalse(in_progress)
        self.assertEquals(scores, {
            u'block@openassessment@000': {
                'display_name': 'display_name',
                'rubrics': {
                    'Final_Score': {
                        u'0-5': [0, 0],
                        u'6-10': [0, 1],
                        u'11-15': [0, 2],
                        u'16-20': [0, 3],
                        u'21-25': [1, 4],
                        u'26-30': [0, 5],
                        u'31-35': [0, 6],
                        u'36-40': [0, 7],
                        u'41-45': [0, 8],
                        u'46-50': [0, 9]
                    }
                }
            },
            u'block@openassessment@999': {
                'display_name': 'display_name',
                'rubrics': {
                    'Final_Score': {
                        u'0-1': [0, 0],
                        u'2-2': [0, 1],
                        u'3-3': [0, 2],
                        u'4-4': [0, 3],
                        u'5-5': [1, 4],
                        u'6-6': [0, 5],
                        u'7-7': [0, 6],
                        u'8-8': [1, 7]
                    }
                }
            }
        })


class AjaxRequestTestCase(ModuleStoreTestCase):
    """"""
    def setUp(self):
        super(AjaxRequestTestCase, self).setUp()

        self.course = CourseFactory.create(display_name='ajax_test')
        self.progress_list_url = reverse(
            'get_progress_list',
            kwargs={'course_id': self.course.id.to_deprecated_string()})
        self.submission_scores_url = reverse(
            'get_submission_scores',
            kwargs={'course_id': self.course.id.to_deprecated_string()})
        self.oa_rubric_scores_url = reverse(
            'get_oa_rubric_scores',
            kwargs={'course_id': self.course.id.to_deprecated_string()})

        self.instructor = InstructorFactory(course_key=self.course.id)
        self.client.login(username=self.instructor.username, password='test')

    def test_ajax_get_progress_list(self):
        response = self.client.get(self.progress_list_url, {})
        self.assertIn("X-Cache-Date", response)
        self.assertEquals(response.status_code, 200)

    def test_ajax_get_oa_rubric_scores(self):
        response = self.client.get(self.oa_rubric_scores_url, {})
        self.assertIn("X-Cache-Date", response)
        self.assertEquals(response.status_code, 200)

    def test_ajax_get_submission_scores(self):
        response = self.client.get(self.submission_scores_url, {})
        self.assertIn("X-Cache-Date", response)
        self.assertEquals(response.status_code, 200)

    @patch('pgreport.views.cache')
    def test_in_progress(self, cache_mock):
        cache_mock.get.return_value = (None, "date", True)
        response = self.client.get(self.progress_list_url, {})
        self.assertEquals(response["X-Cache-Date"], "date")
        self.assertEquals(response.status_code, 202)
