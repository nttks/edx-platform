"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
import csv
import ddt
import json
from mock import MagicMock, patch
import os
import shutil

from courseware.tests.factories import StudentModuleFactory
from django.core.management import call_command, CommandError
from django.test.utils import override_settings
from django.utils.translation import ugettext as _
from student.tests.factories import UserFactory, CourseEnrollmentFactory
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


@override_settings(AWS_ACCESS_KEY_ID='', AWS_SECRET_ACCESS_KEY='')
@ddt.ddt
class DumpBizAnswerDataTest(ModuleStoreTestCase):

    COMMAND_NAME = 'dump_biz_answer_data'
    FILE_NAME = 'dump_biz_answer_data'
    TEMP_DIR = '/tmp/{}'.format(FILE_NAME)
    COURSE_NAME = 'test_course'
    COURSE_ORG = 'org'
    COURSE_RUN = 'run'
    CHAPTER_NAME = 'Week1'
    SEQUENTIAL_NAME = 'Lesson1'
    VERTICAL_NAME = 'Unit1'
    PROBLEM_X_NAME = 'Problem_x'
    PROBLEM_Y_NAME = 'Problem_y'
    HEADER_PREFIX = '{}___{}'.format(CHAPTER_NAME, SEQUENTIAL_NAME)

    def setUp(self):
        super(DumpBizAnswerDataTest, self).setUp()

        self.course = CourseFactory.create(course=self.COURSE_NAME, org=self.COURSE_ORG, run=self.COURSE_RUN)
        self.chapter = ItemFactory.create(
            parent_location=self.course.location,
            category='chapter',
            display_name=self.CHAPTER_NAME
        )
        self.chapter.save()

        self.sequential = ItemFactory.create(
            parent_location=self.chapter.location,
            category='sequential',
            display_name=self.SEQUENTIAL_NAME
        )
        self.sequential.save()

        self.vertical = ItemFactory.create(
            parent_location=self.sequential.location,
            category='vertical',
            display_name=self.VERTICAL_NAME
        )
        self.vertical.save()

        self.problem_x = ItemFactory.create(
            parent_location=self.vertical.location,
            category='problem',
            display_name=self.PROBLEM_X_NAME
        )
        self.problem_x.save()

        self.problem_y = ItemFactory.create(
            parent_location=self.vertical.location,
            category='problem',
            display_name=self.PROBLEM_Y_NAME
        )
        self.problem_y.save()
        self.course.save()

    def tearDown(self):
        super(DumpBizAnswerDataTest, self).tearDown()

        if os.path.exists(self.TEMP_DIR):
            shutil.rmtree(self.TEMP_DIR)

    def test_no_course_id(self):
        error_message = "This command requires one arguments: |<course_id>|"
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME)
        self.assertEqual(e.exception.message, error_message)

    def test_too_much_args(self):
        error_message = "This command requires one arguments: |<course_id>|"
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME, unicode(self.course.id), 'too_much_args')
        self.assertEqual(e.exception.message, error_message)

    def test_invalid_course_id(self):
        error_message = "The course_id is not of the right format. It should be like 'course-v1:org+course+run'"
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME, 'invalid-course-id')
        self.assertEqual(e.exception.message, error_message)

    def test_connection_error(self):
        error_message = "Could not establish a connection to S3 for file upload. Check your credentials."
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME, unicode(self.course.id))
        self.assertEqual(e.exception.message, error_message)

    @patch('biz.djangoapps.ga_achievement.management.commands.dump_biz_answer_data.Key')
    @patch('biz.djangoapps.ga_achievement.management.commands.dump_biz_answer_data.connect_s3')
    def test_s3_error(self, mock_connect_s3, mock_key):
        mock_key.return_value.set_contents_from_filename.side_effect = Exception()
        error_message = "Upload to S3 failed"
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME, unicode(self.course.id))
        self.assertEqual(e.exception.message, error_message)

    @patch('biz.djangoapps.ga_achievement.management.commands.dump_biz_answer_data.connect_s3')
    def test_csv_error(self, mock_connect_s3):
        # Note: By setting filename greater than 255 bytes, IOError is occurred
        error_name = 'a' * 255
        error_message = "Error writing to file: {}/{}_{}_{}_{}.csv".format(self.TEMP_DIR, self.COURSE_ORG, error_name, self.COURSE_RUN, self.FILE_NAME)
        course = CourseFactory.create(course=error_name, org=self.COURSE_ORG, run=self.COURSE_RUN)
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME, unicode(course.id))
        self.assertEqual(e.exception.message, error_message)

    def test_no_such_course_key(self):
        error_message = "Course with {}/{}/{} key not found.".format(self.COURSE_ORG, self.COURSE_NAME, self.COURSE_RUN)
        modulestore().get_course = MagicMock(return_value=None)
        with self.assertRaises(CommandError) as e:
            call_command(self.COMMAND_NAME, unicode(self.course.id))
        self.assertEqual(e.exception.message, error_message)

    @patch('os.remove')
    @patch('biz.djangoapps.ga_achievement.management.commands.dump_biz_answer_data.connect_s3')
    @ddt.data(
        ('student1', True, False, '1', 'correct', '1', 'correct', 'correct', 'correct'),
        ('student2', True, False, '1', 'incorrect', '1', 'incorrect', 'incorrect', 'incorrect'),
        ('student3', True, False, '2', 'correct', '2', 'incorrect', 'incorrect', 'correct'),
        ('student4', True, False, '3', 'correct', '3', 'correct', 'correct', 'incorrect'),
        ('student5', False, False, '', '', '', '', '', ''),
        ('student6', False, True, '', '', '', '', '', ''),
    )
    @ddt.unpack
    def test_success(self, username, answered, skipped, px_attempts, px_correctness, py_attempts, py_correctness1, py_correctness2, py_correctness3, mock_connect_s3, mock_os):
        self._create_student_module_record(username, answered, skipped, px_attempts, px_correctness, py_attempts, py_correctness1, py_correctness2, py_correctness3)
        call_command(self.COMMAND_NAME, unicode(self.course.id))

        if not os.path.exists(self.TEMP_DIR):
            os.makedirs(self.TEMP_DIR)
        filename = '{}_{}_{}_{}.csv'.format(self.COURSE_ORG, self.COURSE_NAME, self.COURSE_RUN, self.FILE_NAME)
        path = os.path.join(self.TEMP_DIR, filename)
        with open(path, 'rb') as f:
            csv_data = [row for row in csv.reader(f)]

        self.assertItemsEqual(csv_data, [
            [_('Username'),  # header line
             '{}___{}___{}'.format(self.HEADER_PREFIX, self.PROBLEM_X_NAME, _('Submit Count')),
             '{}___{}___{}'.format(self.HEADER_PREFIX, self.PROBLEM_X_NAME, _('Final Judgement')),
             '{}___{}___{}'.format(self.HEADER_PREFIX, self.PROBLEM_Y_NAME, _('Submit Count')),
             '{}___{}___{}'.format(self.HEADER_PREFIX, self.PROBLEM_Y_NAME, _('Final Judgement'))],
            [username,  # record line
             px_attempts,
             self._create_answer_problem_x(px_correctness),
             py_attempts,
             self._create_answer_problem_y(py_correctness1, py_correctness2, py_correctness3)],
        ])

    def _create_student_module_record(self, username, answered, skipped, px_attempts, px_correctness, py_attempts, py_correctness1, py_correctness2, py_correctness3):
        self.student = UserFactory.create(username=username)
        CourseEnrollmentFactory.create(user=self.student, course_id=self.course.id)

        # course
        StudentModuleFactory.create(
            student=self.student,
            course_id=self.course.id,
            module_type='course',
            module_state_key=self.course.location
        )
        # chapter
        StudentModuleFactory.create(
            student=self.student,
            course_id=self.course.id,
            module_type='chapter',
            module_state_key=self.chapter.location
        )
        # sequential
        StudentModuleFactory.create(
            student=self.student,
            course_id=self.course.id,
            module_type='sequential',
            module_state_key=self.sequential.location
        )

        if not skipped:
            # problem_x
            correct_map = self._make_correct_map_single(self.problem_x, px_attempts, px_correctness) if answered else self._make_no_answer_data()
            StudentModuleFactory.create(
                grade=1,
                max_grade=1,
                student=self.student,
                course_id=self.course.id,
                module_type='problem',
                module_state_key=self.problem_x.location,
                state=correct_map
            )
            # problem_y
            correct_map = self._make_correct_map_multi(self.problem_y, py_attempts, py_correctness1, py_correctness2, py_correctness3) if answered else self._make_no_answer_data()
            StudentModuleFactory.create(
                grade=1,
                max_grade=1,
                student=self.student,
                course_id=self.course.id,
                module_type='problem',
                module_state_key=self.problem_y.location,
                state=correct_map
            )

    @staticmethod
    def _make_no_answer_data():
        return json.dumps({"position": 1})

    @staticmethod
    def _make_correct_map_single(problem, attempts, correctness):
        correct_map = {
            unicode(problem.location) + "_2_1": {
                "hint": "",
                "hintmode": "",
                "correctness": correctness,
                "npoints": "",
                "msg": "",
                "queuestate": ""
            }
        }
        return json.dumps({"attempts": attempts, "seed": 1, "done": True, "correct_map": correct_map})

    @staticmethod
    def _make_correct_map_multi(problem, attempts, correctness1, correctness2, correctness3):
        correct_map = {
            unicode(problem.location) + "_2_1": {
                "hint": "",
                "hintmode": "",
                "correctness": correctness1,
                "npoints": "",
                "msg": "",
                "queuestate": ""
            },
            unicode(problem.location) + "_3_1": {
                "hint": "",
                "hintmode": "",
                "correctness": correctness2,
                "npoints": "",
                "msg": "",
                "queuestate": ""
            },
            unicode(problem.location) + "_4_1": {
                "hint": "",
                "hintmode": "",
                "correctness": correctness3,
                "npoints": "",
                "msg": "",
                "queuestate": ""
            }
        }
        return json.dumps({"attempts": attempts, "seed": 1, "done": True, "correct_map": correct_map})

    @staticmethod
    def _create_answer_problem_x(correctness):
        if correctness == 'correct':
            return '1(1)'
        elif correctness == 'incorrect':
            return '0(1)'
        else:
            return ''

    @staticmethod
    def _create_answer_problem_y(correctness1, correctness2, correctness3):
        if correctness1 == correctness2 == correctness3 == '':
            return ''

        count_correct = 0
        if 'correct' == correctness1:
            count_correct += 1
        if 'correct' == correctness2:
            count_correct += 1
        if 'correct' == correctness3:
            count_correct += 1
        return '{}(3)'.format(count_correct)
