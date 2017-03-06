import ddt
from mock import patch

from django.test import TestCase
from django.test.utils import override_settings

from certificates.tests.factories import GeneratedCertificateFactory
from ga_operation.tasks import create_certs_task
from opaque_keys.edx.keys import CourseKey
from pdfgen.certificate import CertPDFException, CertPDFUserNotFoundException
from pdfgen.views import CertException
from student.tests.factories import UserFactory


@ddt.ddt
@override_settings(GA_OPERATION_EMAIL_SENDER='sender@example.com')
class CreateCertsTest(TestCase):

    def _setup_certificate(self, course_id):
        for status in [
            'deleted', 'deleting', 'downloadable', 'error', 'generating',
            'notpassing', 'regenerating', 'restricted', 'unavailable',
        ]:
            self._create_certificate(course_id, status, '{}-certificate'.format(status))
            self._create_certificate(course_id + 'X', status, '{}-certificateX'.format(status))

    def _create_certificate(self, course_id, status, download_url='', user=None):
        if user is None:
            user = UserFactory.create()
        course_key = CourseKey.from_string(course_id)
        return GeneratedCertificateFactory.create(user=user, course_id=course_key, status=status, download_url=download_url)

    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.send_mail')
    @patch('ga_operation.tasks.call_command')
    def test_run(self, mock_call_command, mock_send_mail, mock_log):
        self._setup_certificate('course-v1:org+course+run')

        create_certs_task('course-v1:org+course+run', 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', 'course-v1:org+course+run',
            username=False, debug=False, noop=False, prefix=''
        )
        mock_send_mail.assert_called_once_with(
            'create_certs was completed.',
            'create_certs(create) was success\ngenerating-certificate',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()

    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.send_mail')
    @patch('ga_operation.tasks.call_command')
    def test_run_with_student_ids(self, mock_call_command, mock_send_mail, mock_log):
        # CertPDFUserNotFoundException occur at second, but still should be continue
        mock_call_command.side_effect = [None, CertPDFUserNotFoundException, None]
        self._setup_certificate('course-v1:org+course+run')

        create_certs_task('course-v1:org+course+run', 'test@example.com', ['user1', 'user2', 'user3'], 'verified-')

        self.assertEqual(mock_call_command.call_count, 3)
        for user in ['user1', 'user2', 'user3']:
            mock_call_command.assert_any_call(
                'create_certs', 'create', 'course-v1:org+course+run',
                username=user, debug=False, noop=False, prefix='verified-'
            )
        mock_send_mail.assert_called_once_with(
            'create_certs was completed.',
            'create_certs(create) was success\ngenerating-certificate',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.warning.assert_called_once_with('User(user2) was not found')
        mock_log.exception.assert_not_called()

    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(CertException, CertPDFException)
    def test_run_generate_error(self, exception, mock_call_command, mock_send_mail, mock_log):
        # CertPDFException occur at second, then should not be continue
        mock_call_command.side_effect = [None, exception, None]
        self._setup_certificate('course-v1:org+course+run')

        create_certs_task('course-v1:org+course+run', 'test@example.com', ['user1', 'user2', 'user3'])

        self.assertEqual(mock_call_command.call_count, 2)
        for user in ['user1', 'user2']:
            mock_call_command.assert_any_call(
                'create_certs', 'create', 'course-v1:org+course+run',
                username=user, debug=False, noop=False, prefix=''
            )
        mock_call_command.assert_not_called(
            'create_certs', 'create', 'course-v1:org+course+run',
            username='user3', debug=False, noop=False, prefix=''
        )

        mock_send_mail.assert_called_once_with(
            'create_certs was failure',
            'create_certs(create) was failed.\n\nFailure to generate the PDF files from create_certs command. ',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_called_once_with('Failure to generate the PDF files from create_certs command.')

    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.send_mail')
    @patch('ga_operation.tasks.call_command')
    def test_run_unknown_error(self, mock_call_command, mock_send_mail, mock_log):
        # Exception occur at second, then should not be continue
        mock_call_command.side_effect = [None, Exception, None]
        self._setup_certificate('course-v1:org+course+run')

        create_certs_task('course-v1:org+course+run', 'test@example.com', ['user1', 'user2', 'user3'])

        self.assertEqual(mock_call_command.call_count, 2)
        for user in ['user1', 'user2']:
            mock_call_command.assert_any_call(
                'create_certs', 'create', 'course-v1:org+course+run',
                username=user, debug=False, noop=False, prefix=''
            )
        mock_call_command.assert_not_called(
            'create_certs', 'create', 'course-v1:org+course+run',
            username='user3', debug=False, noop=False, prefix=''
        )

        mock_send_mail.assert_called_once_with(
            'create_certs was failure',
            'create_certs(create) was failed.\n\nCaught the exception: Exception ',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_called_once_with('Caught the exception: Exception')
