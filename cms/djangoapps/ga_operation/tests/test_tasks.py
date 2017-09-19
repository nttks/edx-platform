# -*- coding: utf-8 -*-
import ddt
from mock import patch, MagicMock, PropertyMock

from django.test import TestCase
from django.test.utils import override_settings

from certificates.tests.factories import GeneratedCertificateFactory
from cms.djangoapps.ga_operation.tasks import delete_course_task, delete_library_task
from opaque_keys.edx.keys import CourseKey
from pdfgen.certificate import CertPDFException, CertPDFUserNotFoundException
from pdfgen.views import CertException
from student.tests.factories import CourseEnrollmentFactory, UserStandingFactory
from student.tests.factories import UserFactory


@ddt.ddt
@override_settings(GA_OPERATION_EMAIL_SENDER='sender@example.com')
class DeleteCourseTest(TestCase):

    def setUp(self):
        super(DeleteCourseTest, self).setUp()
        self.course_id = 'course-v1:org+course+run'

    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('cms.djangoapps.ga_operation.tasks.log')
    @patch('cms.djangoapps.ga_operation.tasks.change_behavior_sys')
    @patch('cms.djangoapps.ga_operation.tasks.call_command')
    def test_run(self, mock_call_command, mock_change_behavior_sys, mock_log, mock_send_mail):
        delete_course_task(self.course_id, 'test@example.com')

        self.assertTrue(mock_call_command.called_once)
        self.assertTrue(mock_change_behavior_sys.called_once)
        mock_call_command.assert_any_call(
            'delete_course', self.course_id, "--purge"
        )

        mock_send_mail.assert_called_once_with(
            'delete_course was completed. ({})'.format(self.course_id),
            'delete_course was succeeded.\n\n',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        self.assertTrue(mock_log.exception.assert_not_called())

    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('cms.djangoapps.ga_operation.tasks.log')
    @patch('cms.djangoapps.ga_operation.tasks.change_behavior_sys')
    @patch('cms.djangoapps.ga_operation.tasks.call_command')
    def test_run_unknown_error(self, mock_call_command, mock_change_behavior_sys, mock_log, mock_send_mail):
        # Exception occur at second, then should not be continue
        mock_call_command.side_effect = [Exception]

        delete_course_task(self.course_id, 'test@example.com')

        self.assertTrue(mock_call_command.called_once)
        self.assertTrue(mock_change_behavior_sys.called_once)
        mock_call_command.assert_any_call(
            'delete_course', self.course_id, "--purge"
        )

        mock_send_mail.assert_called_once_with(
            'delete_course was failure ({})'.format(self.course_id),
            'Caught the exception: Exception ',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_called_once_with('Caught the exception: Exception')


@ddt.ddt
@override_settings(GA_OPERATION_EMAIL_SENDER='sender@example.com')
class DeleteLibraryTest(TestCase):

    def setUp(self):
        super(DeleteLibraryTest, self).setUp()
        self.course_id = 'course-v1:org+course+run'

    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('cms.djangoapps.ga_operation.tasks.log')
    @patch('cms.djangoapps.ga_operation.tasks.change_behavior_sys')
    @patch('cms.djangoapps.ga_operation.tasks.call_command')
    def test_run(self, mock_call_command, mock_change_behavior_sys, mock_log, mock_send_mail):
        delete_library_task(self.course_id, 'test@example.com')

        self.assertTrue(mock_call_command.called_once)
        self.assertTrue(mock_change_behavior_sys.called_once)
        mock_call_command.assert_any_call(
            'delete_library', self.course_id, "--purge"
        )

        mock_send_mail.assert_called_once_with(
            'delete_library was completed. ({})'.format(self.course_id),
            'delete_library was succeeded.\n\n',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        self.assertTrue(mock_log.exception.assert_not_called())

    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('cms.djangoapps.ga_operation.tasks.log')
    @patch('cms.djangoapps.ga_operation.tasks.change_behavior_sys')
    @patch('cms.djangoapps.ga_operation.tasks.call_command')
    def test_run_unknown_error(self, mock_call_command, mock_change_behavior_sys, mock_log, mock_send_mail):
        # Exception occur at second, then should not be continue
        mock_call_command.side_effect = [Exception]

        delete_library_task(self.course_id, 'test@example.com')

        self.assertTrue(mock_call_command.called_once)
        self.assertTrue(mock_change_behavior_sys.called_once)
        mock_call_command.assert_any_call(
            'delete_library', self.course_id, "--purge"
        )

        mock_send_mail.assert_called_once_with(
            'delete_library was failure ({})'.format(self.course_id),
            'Caught the exception: Exception ',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_called_once_with('Caught the exception: Exception')
