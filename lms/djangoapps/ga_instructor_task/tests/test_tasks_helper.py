# -*- coding: utf-8 -*-
"""
Unit tests for LMS instructor-initiated background tasks helper functions.

Tests that CSV Gacco's report generation works.
"""
from mock import MagicMock, patch

from django.utils.translation import ugettext as _
from ga_instructor_task.ga_instructor_report_record import GaScoreDetailReportRecord, GaPlaybackStatusReportRecord
from ga_instructor_task.tasks_helper import (
    generate_score_detail_report_helper,
    generate_playback_status_report_helper,
)
from instructor_task.tests.test_base import TestReportMixin, InstructorTaskModuleTestCase
from opaque_keys.edx.keys import CourseKey
from student.models import (
    CourseEnrollment,
    UserStanding,
)
from student.roles import (
    CourseStaffRole,
    CourseInstructorRole,
)
from student.tests.factories import UserFactory, CourseModeFactory, UserStandingFactory
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory


class TestScoreDetailReport(TestReportMixin, InstructorTaskModuleTestCase):
    """
    Test that the score detail report CSV generation works.
    """
    def setUp(self):
        super(TestScoreDetailReport, self).setUp()
        self.action_name = 'score detail report generated'
        self.course = CourseFactory.create()

        self.csv_header_row = [
            _(GaScoreDetailReportRecord.FIELD_USERNAME),
            _(GaScoreDetailReportRecord.FIELD_EMAIL),
            _(GaScoreDetailReportRecord.FIELD_GLOBAL_STAFF),
            _(GaScoreDetailReportRecord.FIELD_COURSE_ADMIN),
            _(GaScoreDetailReportRecord.FIELD_COURSE_STAFF),
            _(GaScoreDetailReportRecord.FIELD_ENROLL_STATUS),
            _(GaScoreDetailReportRecord.FIELD_ENROLL_DATE),
            _(GaScoreDetailReportRecord.FIELD_RESIGN_STATUS),
            _(GaScoreDetailReportRecord.FIELD_RESIGN_DATE),
            _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE),
        ]

    def add_grading_policy(self, grading_policy, user):
        """
        Add a grading policy to the course.
        cf. lms/djangoapps/courseware/tests/test_submitting_problem.py
        """
        self.course.grading_policy = grading_policy
        self.update_course(self.course, user.id)

    def _create_simple_structure(self):
        # Add block to the course
        self.chapter1 = ItemFactory.create(parent_location=self.course.location, display_name='chapter1')
        self.section1 = ItemFactory.create(parent_location=self.chapter1.location, category='sequential',
                                           metadata={'graded': True, 'format': 'Homework'}, display_name='section1')
        self.vertical1 = ItemFactory.create(parent_location=self.section1.location, category='vertical',
                                            metadata={'graded': True}, display_name='Problem Vertical1')
        self.define_option_problem(u'Pröblem1', parent=self.vertical1)

    @staticmethod
    def _get_grading_policy_for_simple():
        return {
            "GRADER": [{
                "type": "Homework",
                "min_count": 1,
                "drop_count": 0,
                "short_label": "HW",
                "weight": 1.0
            }]
        }

    def _create_multiple_structure(self):
        # Add block to the course
        # -> course
        #    -> chapter1
        #       -> section1-1
        #          -> vertical1-1-1
        #             -> problem1-1-1
        #          -> vertical1-1-2
        #             -> problem1-1-2
        #       -> section1-2
        #          -> vertical1-2-1
        #             -> problem1-2-1
        #    -> chapter2
        #       -> section2-1
        #          -> vertical2-1-1
        #             -> problem2-1-1
        #          -> vertical2-1-2
        #             -> problem2-1-2
        #
        self.chapter1 = ItemFactory.create(parent_location=self.course.location, display_name='chapter1')
        self.section1_1 = ItemFactory.create(parent_location=self.chapter1.location, category='sequential',
                                             metadata={'graded': True, 'format': 'Homework'}, display_name='section1-1')
        self.vertical1_1_1 = ItemFactory.create(parent_location=self.section1_1.location, category='vertical',
                                                metadata={'graded': True}, display_name='Problem Vertical1-1-1')
        self.define_option_problem(u'Pröblem1-1-1', parent=self.vertical1_1_1)

        self.vertical1_1_2 = ItemFactory.create(parent_location=self.section1_1.location, category='vertical',
                                                metadata={'graded': True}, display_name='Problem Vertical1-1-2')
        self.define_option_problem(u'Pröblem1-1-2', parent=self.vertical1_1_2)

        self.section1_2 = ItemFactory.create(parent_location=self.chapter1.location, category='sequential',
                                             metadata={'graded': True, 'format': 'Midterm Exam'}, display_name='section1-2')
        self.vertical1_2_1 = ItemFactory.create(parent_location=self.section1_2.location, category='vertical',
                                                metadata={'graded': True}, display_name='Problem Vertical1-2-1')
        self.define_option_problem(u'Pröblem1-2-1', parent=self.vertical1_2_1)

        self.chapter2 = ItemFactory.create(parent_location=self.course.location, display_name='chapter2')
        self.section2_1 = ItemFactory.create(parent_location=self.chapter2.location, category='sequential',
                                             metadata={'graded': True, 'format': 'Final Exam'}, display_name='section2-1')
        self.vertical2_1_1 = ItemFactory.create(parent_location=self.section2_1.location, category='vertical',
                                                metadata={'graded': True}, display_name='Problem Vertical2-1-1')
        self.define_option_problem(u'Pröblem2-1-1', parent=self.vertical2_1_1)

        self.vertical2_1_2 = ItemFactory.create(parent_location=self.section2_1.location, category='vertical',
                                                metadata={'graded': True}, display_name='Problem Vertical2-1-2')
        self.define_option_problem(u'Pröblem2-1-2', parent=self.vertical2_1_2)

    @staticmethod
    def _get_grading_policy_for_multiple():
        return {
            "GRADER": [
                {
                    "type": "Homework",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "HW",
                    "weight": 0.4
                },
                {
                    "type": "Midterm Exam",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "Midterm",
                    "weight": 0.2
                },
                {
                    "type": "Final Exam",
                    "min_count": 1,
                    "drop_count": 0,
                    "short_label": "Final",
                    "weight": 0.4
                },
            ]
        }

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_course_does_not_exist(self, _get_current_task):
        not_exist_course_id = CourseKey.from_string('course-v1:not+exist+course')
        result = generate_score_detail_report_helper(None, None, not_exist_course_id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 0, 'failed': 1, 'step': 'Not exist course'},
            result)

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_error(self, _get_current_task):
        with patch('student.models.CourseEnrollment.objects.enrolled_and_dropped_out_users', MagicMock(return_value=Exception('DUMMY ERROR'))):
            result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
            self.assertDictContainsSubset(
                {'action_name': self.action_name, 'attempted': 0, 'succeeded': 0, 'failed': 1, 'step': 'Error'},
                result)

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_with_single_problem(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        student2 = self.create_student(username="student2", email="student2@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)
        enroll2 = CourseEnrollment.get_enrollment(student2, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_simple(), student1)
        self._create_simple_structure()

        # Respondent is student1 only
        self.submit_student_answer(student1.username, u'Pröblem1', ['Option 1', 'Option 1'])

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 2, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'100.0%',
                    u'100.0%',   # see: TestProblemGradeReport:test_single_problem()
                    u'2.0'
                ]
            )),
            dict(zip(
                header_row,
                [
                    u'{}'.format(student2.username),
                    u'{}'.format(student2.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll
                    u'{}'.format(enroll2.created if enroll2.is_active else ''),
                    u'0',  # student2.is_active -> 0
                    u'',
                    u'0.0%',
                    u'',
                    u'0.0'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_unenroll_user(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_simple(), student1)
        self._create_simple_structure()

        self.submit_student_answer(student1.username, u'Pröblem1', ['Option 1'])

        # Unenroll
        enroll1.deactivate()

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'0',  # unenroll
                    u'{}'.format(enroll1.created),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'50.0%',
                    u'50.0%',
                    u'1.0'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_resign_user(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_simple(), student1)
        self._create_simple_structure()

        self.submit_student_answer(student1.username, u'Pröblem1', ['Option 1'])

        # Disable account
        user1_standing = UserStandingFactory.create(
            user=student1,
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=student1,
        )

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll
                    u'{}'.format(enroll1.created),
                    u'1',  # student1.is_active -> 0
                    u'{}'.format(user1_standing.standing_last_changed_at),
                    u'50.0%',
                    u'50.0%',
                    u'1.0'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_global_staff(self, _get_current_task):
        student1 = self.create_instructor(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_simple(), student1)
        self._create_simple_structure()

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'1',  # is_staff
                    u'1',  # course instructor
                    u'1',  # course staff
                    u'1',  # enroll
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'0.0%',
                    u'',
                    u'0.0'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_course_instructor(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        CourseInstructorRole(self.course.id).add_users(student1)
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_simple(), student1)
        self._create_simple_structure()

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'1',  # course instructor
                    u'1',  # course staff
                    u'1',  # enroll
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # is_acitve -> 0
                    u'',
                    u'0.0%',
                    u'',
                    u'0.0'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_course_staff(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        CourseStaffRole(self.course.id).add_users(student1)
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_simple(), student1)
        self._create_simple_structure()

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'1',  # course staff
                    u'1',  # enroll
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # is_active -> 0
                    u'',
                    u'0.0%',
                    u'',
                    u'0.0'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_with_multiple_problem(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self.add_grading_policy(self._get_grading_policy_for_multiple(), student1)
        self._create_multiple_structure()

        self.submit_student_answer(student1.username, u'Pröblem1-1-1', ['Option 1', 'Option 1'])
        self.submit_student_answer(student1.username, u'Pröblem1-1-2', ['Option 1'])
        self.submit_student_answer(student1.username, u'Pröblem1-2-1', ['Option 1'])
        self.submit_student_answer(student1.username, u'Pröblem2-1-1', ['Option 1'])
        self.submit_student_answer(student1.username, u'Pröblem2-1-2', ['Option 1'])

        result = generate_score_detail_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___section1-1',
            u'chapter1___section1-2',
            '{}{}{}'.format(u'chapter1', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
            u'chapter2___section2-1',
            '{}{}{}'.format(u'chapter2', u'___', _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'{}'.format(1 if student1.is_staff else 0),
                    u'0',
                    u'0',
                    u'1',
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',
                    u'',
                    u'60.0%',
                    u'75.0%',   # section1-1
                    u'50.0%',   # section1-2
                    u'4.0',     # chapter1
                    u'50.0%',   # section2-1
                    u'2.0',     # chapter2
                ]
            )),
        ])


class TestPlaybackStatusReport(TestReportMixin, InstructorTaskModuleTestCase):
    """
    Test that the playback status report CSV generation works.
    """
    def setUp(self):
        super(TestPlaybackStatusReport, self).setUp()
        self.action_name = 'playback status report generated'
        self.course = CourseFactory.create()

        self.csv_header_row = [
            _(GaPlaybackStatusReportRecord.FIELD_USERNAME),
            _(GaPlaybackStatusReportRecord.FIELD_EMAIL),
            _(GaPlaybackStatusReportRecord.FIELD_GLOBAL_STAFF),
            _(GaPlaybackStatusReportRecord.FIELD_COURSE_ADMIN),
            _(GaPlaybackStatusReportRecord.FIELD_COURSE_STAFF),
            _(GaPlaybackStatusReportRecord.FIELD_ENROLL_STATUS),
            _(GaPlaybackStatusReportRecord.FIELD_ENROLL_DATE),
            _(GaPlaybackStatusReportRecord.FIELD_RESIGN_STATUS),
            _(GaPlaybackStatusReportRecord.FIELD_RESIGN_DATE),
            _(GaPlaybackStatusReportRecord.FIELD_TOTAL_PLAYBACK_TIME),
        ]

        # Setup mock
        patcher_aggregate = patch('biz.djangoapps.ga_achievement.log_store.PlaybackLogStore.aggregate')
        self.mock_aggregate = patcher_aggregate.start()
        self.mock_aggregate.return_value = {}
        self.addCleanup(patcher_aggregate.stop)

    def _create_simple_structure(self):
        # Add block to the course
        self.chapter1 = ItemFactory.create(parent_location=self.course.location, display_name='chapter1')
        self.section1 = ItemFactory.create(parent_location=self.chapter1.location, category='sequential', display_name='section1')
        self.vertical1 = ItemFactory.create(parent_location=self.section1.location, category='vertical', display_name='Video Vertical1')
        self.component1 = ItemFactory.create(parent=self.vertical1, category='jwplayerxblock', display_name='component1')

    def _create_multiple_structure(self):
        # Add block to the course
        # -> course
        #    -> chapter1
        #       -> section1-1
        #          -> vertical1-1-1
        #             -> problem1-1-1
        #          -> vertical1-1-2
        #             -> problem1-1-2
        #       -> section1-2
        #          -> vertical1-2-1
        #             -> problem1-2-1
        #    -> chapter2
        #       -> section2-1
        #          -> vertical2-1-1
        #             -> problem2-1-1
        #
        self.chapter1 = ItemFactory.create(parent_location=self.course.location, display_name='chapter1')
        self.section1_1 = ItemFactory.create(parent_location=self.chapter1.location, category='sequential', display_name='section1-1')
        self.vertical1_1_1 = ItemFactory.create(parent_location=self.section1_1.location, category='vertical', display_name='Video Vertical1-1-1')
        self.component1_1_1 = ItemFactory.create(parent=self.vertical1_1_1, category='jwplayerxblock', display_name='component1-1-1')

        self.vertical1_1_2 = ItemFactory.create(parent_location=self.section1_1.location, category='vertical', display_name='Video Vertical1-1-2')
        self.component1_1_2 = ItemFactory.create(parent=self.vertical1_1_2, category='jwplayerxblock', display_name='component1-1-2')

        self.section1_2 = ItemFactory.create(parent_location=self.chapter1.location, category='sequential', display_name='section1-2')
        self.vertical1_2_1 = ItemFactory.create(parent_location=self.section1_2.location, category='vertical', display_name='Video Vertical1-2-1')
        self.component1_2_1 = ItemFactory.create(parent=self.vertical1_2_1, category='jwplayerxblock', display_name='component1-2-1')

        self.chapter2 = ItemFactory.create(parent_location=self.course.location, display_name='chapter2')
        self.section2_1 = ItemFactory.create(parent_location=self.chapter2.location, category='sequential', display_name='section2-1')
        self.vertical2_1_1 = ItemFactory.create(parent_location=self.section2_1.location, category='vertical', display_name='Video Vertical2-1-1')
        self.component2_1_1 = ItemFactory.create(parent=self.vertical2_1_1, category='jwplayerxblock', display_name='component2-1-1')

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_course_does_not_exist(self, _get_current_task):
        not_exist_course_id = CourseKey.from_string('course-v1:not+exist+course')
        result = generate_playback_status_report_helper(None, None, not_exist_course_id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 0, 'failed': 1, 'step': 'Not exist course'},
            result)

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_error(self, _get_current_task):
        with patch('student.models.CourseEnrollment.objects.enrolled_and_dropped_out_users', MagicMock(return_value=Exception('DUMMY ERROR'))):
            result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
            self.assertDictContainsSubset(
                {'action_name': self.action_name, 'attempted': 0, 'succeeded': 0, 'failed': 1, 'step': 'Error'},
                result)

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_with_single_video(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        student2 = self.create_student(username="student2", email="student2@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)
        enroll2 = CourseEnrollment.get_enrollment(student2, self.course.id)

        self._create_simple_structure()

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1.location.block_id): 100.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 2, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'0:02',
                    u'0:02',
                    u'0:02'
                ]
            )),
            dict(zip(
                header_row,
                [
                    u'{}'.format(student2.username),
                    u'{}'.format(student2.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll
                    u'{}'.format(enroll2.created if enroll2.is_active else ''),
                    u'0',  # student2.is_active -> 0
                    u'',
                    u'0:02',
                    u'0:02',
                    u'0:02'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_with_single_video_no_data(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_simple_structure()

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'0:00',
                    u'',
                    u'0:00'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_unenroll_user(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_simple_structure()

        # Unenroll
        enroll1.deactivate()

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1.location.block_id): 20.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'0',  # enroll1.is_active
                    u'{}'.format(enroll1.created),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'0:01',
                    u'0:01',
                    u'0:01'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_resign_user(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_simple_structure()

        # Disable account
        user1_standing = UserStandingFactory.create(
            user=student1,
            account_status=UserStanding.ACCOUNT_DISABLED,
            changed_by=student1,
        )

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1.location.block_id): 181.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'1',  # student1.is_active -> 0
                    u'{}'.format(user1_standing.standing_last_changed_at),
                    u'0:04',
                    u'0:04',
                    u'0:04'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_global_staff(self, _get_current_task):
        student1 = self.create_instructor(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_simple_structure()

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1.location.block_id): 2000.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'1',  # is_staff
                    u'1',  # course instructor
                    u'1',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'0:34',
                    u'0:34',
                    u'0:34'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_course_instructor(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        CourseInstructorRole(self.course.id).add_users(student1)
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_simple_structure()

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1.location.block_id): 3601.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'1',  # course instructor
                    u'1',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'1:01',
                    u'1:01',
                    u'1:01'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_course_staff(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        CourseStaffRole(self.course.id).add_users(student1)
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_simple_structure()

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1.location.block_id): 125760.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'1',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'34:56',
                    u'34:56',
                    u'34:56'
                ]
            )),
        ])

    @patch('instructor_task.tasks_helper._get_current_task')
    def test_success_with_multiple_video(self, _get_current_task):
        student1 = self.create_student(username="student1", email="student1@example.com")
        enroll1 = CourseEnrollment.get_enrollment(student1, self.course.id)

        self._create_multiple_structure()

        _aggregate_duration_by_vertical = {
            u'{}'.format(self.vertical1_1_1.location.block_id): 30.0,
            u'{}'.format(self.vertical1_1_2.location.block_id): 120.0,
            u'{}'.format(self.vertical1_2_1.location.block_id): 91.0,
            u'{}'.format(self.vertical2_1_1.location.block_id): 10.0,
        }
        self.mock_aggregate.return_value = _aggregate_duration_by_vertical

        result = generate_playback_status_report_helper(None, None, self.course.id, None, self.action_name)
        self.assertDictContainsSubset(
            {'action_name': self.action_name, 'attempted': 0, 'succeeded': 1, 'failed': 0}, result)

        header_row = self.csv_header_row + [
            u'chapter1___Video Vertical1-1-1',
            u'chapter1___Video Vertical1-1-2',
            u'chapter1___Video Vertical1-2-1',
            '{}{}{}'.format(u'chapter1', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME)),
            u'chapter2___Video Vertical2-1-1',
            '{}{}{}'.format(u'chapter2', u'___', _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME)),
        ]

        self.verify_rows_in_csv([
            dict(zip(
                header_row,
                [
                    u'{}'.format(student1.username),
                    u'{}'.format(student1.email),
                    u'0',  # is_staff
                    u'0',  # course instructor
                    u'0',  # course staff
                    u'1',  # enroll1.is_active
                    u'{}'.format(enroll1.created if enroll1.is_active else ''),
                    u'0',  # student1.is_active -> 0
                    u'',
                    u'0:05',
                    u'0:01',
                    u'0:02',
                    u'0:02',
                    u'0:05',
                    u'0:01',
                    u'0:01',
                ]
            )),
        ])
