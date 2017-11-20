# -*- coding: utf-8 -*-
"""
Test for LMS instructor background task queue management
"""
from courseware.tests.factories import UserFactory
from ga_instructor_task.api import (
    submit_generate_score_detail_report,
    submit_generate_playback_status_report,
)
from instructor_task.api_helper import AlreadyRunningError
from instructor_task.models import InstructorTask, PROGRESS
from instructor_task.tests.test_base import (
    InstructorTaskCourseTestCase,
    TestReportMixin,
)


class GaApiTest(TestReportMixin, InstructorTaskCourseTestCase):
    """Tests API methods that involve the submission of course-based background tasks."""

    def setUp(self):
        super(GaApiTest, self).setUp()

        self.initialize_course()
        self.student = UserFactory.create(username="student", email="student@edx.org")
        self.instructor = UserFactory.create(username="instructor", email="instructor@edx.org")

    def _test_resubmission(self, api_call):
        """
        cf. instructor_task/tests/test_api.py
        """
        instructor_task = api_call()
        instructor_task = InstructorTask.objects.get(id=instructor_task.id)
        instructor_task.task_state = PROGRESS
        instructor_task.save()
        with self.assertRaises(AlreadyRunningError):
            api_call()

    def test_submit_generate_score_detail_report(self):
        api_call = lambda: submit_generate_score_detail_report(
            self.create_task_request(self.instructor),
            self.course.id,
        )
        self._test_resubmission(api_call)

    def test_submit_generate_playback_status_report(self):
        api_call = lambda: submit_generate_playback_status_report(
            self.create_task_request(self.instructor),
            self.course.id,
        )
        self._test_resubmission(api_call)
