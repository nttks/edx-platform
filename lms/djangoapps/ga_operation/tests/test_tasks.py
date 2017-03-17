# -*- coding: utf-8 -*-
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

    def setUp(self):
        super(CreateCertsTest, self).setUp()
        self.course_id = 'course-v1:org+course+run'
        self.users = [UserFactory.create() for __ in range(3)]

    def _setup_certificate(self, course_id):
        # Create certificates except status is generating
        for status in [
            'deleted', 'deleting', 'downloadable', 'error',
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
        self._setup_certificate(self.course_id)
        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed.',
            u'3件の修了証を発行しました\n{}'.format(expected_urls_text),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()

    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.send_mail')
    @patch('ga_operation.tasks.call_command')
    def test_run_with_student_ids(self, mock_call_command, mock_send_mail, mock_log):
        # CertPDFUserNotFoundException occur at first, but still should be continue
        mock_call_command.side_effect = [CertPDFUserNotFoundException, None, None]
        self._setup_certificate(self.course_id)
        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)
        unknown_user = UserFactory.create()

        # Specify user0 and user2 and unknown_user. This means certificate of user1 was already created.
        student_ids = [unknown_user.username, self.users[0].email, self.users[2].username]
        create_certs_task(self.course_id, 'test@example.com', student_ids, 'verified-')

        self.assertEqual(mock_call_command.call_count, 3)
        for user in student_ids:
            mock_call_command.assert_any_call(
                'create_certs', 'create', self.course_id,
                username=user, debug=False, noop=False, prefix='verified-'
            )
        expected_created_urls_text = '\n'.join(['{}-url'.format(user.username) for user in [self.users[0], self.users[2]]])
        expected_all_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed.',
            u'2件の修了証を発行しました\n{}\n\n3件の修了証はまだ公開されていません\n{}'.format(
                expected_created_urls_text, expected_all_urls_text),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.warning.assert_called_once_with('User({}) was not found'.format(unknown_user.username))
        mock_log.exception.assert_not_called()

    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(CertException, CertPDFException)
    def test_run_generate_error(self, exception, mock_call_command, mock_send_mail, mock_log):
        # CertPDFException occur at second, then should not be continue
        mock_call_command.side_effect = [None, exception, None]

        create_certs_task(self.course_id, 'test@example.com', ['user1', 'user2', 'user3'])

        self.assertEqual(mock_call_command.call_count, 2)
        for user in ['user1', 'user2']:
            mock_call_command.assert_any_call(
                'create_certs', 'create', self.course_id,
                username=user, debug=False, noop=False, prefix=''
            )
        mock_call_command.assert_not_called(
            'create_certs', 'create', self.course_id,
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

        create_certs_task(self.course_id, 'test@example.com', ['user1', 'user2', 'user3'])

        self.assertEqual(mock_call_command.call_count, 2)
        for user in ['user1', 'user2']:
            mock_call_command.assert_any_call(
                'create_certs', 'create', self.course_id,
                username=user, debug=False, noop=False, prefix=''
            )
        mock_call_command.assert_not_called(
            'create_certs', 'create', self.course_id,
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
