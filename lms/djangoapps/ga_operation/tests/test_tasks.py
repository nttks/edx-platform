# -*- coding: utf-8 -*-
import ddt
from mock import patch, MagicMock, PropertyMock

from django.test import TestCase
from django.test.utils import override_settings

from certificates.tests.factories import GeneratedCertificateFactory
from ga_operation.tasks import create_certs_task, publish_certs_task
from opaque_keys.edx.keys import CourseKey
from pdfgen.certificate import CertPDFException, CertPDFUserNotFoundException
from pdfgen.views import CertException
from student.models import UserStanding
from student.tests.factories import CourseEnrollmentFactory, UserStandingFactory
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

    def _create_course_enrollment(self, user, course_id):
        course_key = CourseKey.from_string(course_id)
        return CourseEnrollmentFactory.create(user=user, course_id=course_key)

    def _create_user_standing(self, user, account_status):
        return UserStandingFactory.create(user=user, account_status=account_status, changed_by=UserFactory.create())

    def _get_course_mock(self):
        m = MagicMock()
        type(m).id = PropertyMock(return_value=CourseKey.from_string(self.course_id))
        type(m).grade_cutoffs = PropertyMock(return_value={'A': 0.5, 'B': 0.3})
        return m

    def _set_enroll(self, is_active):
        for user in self.users:
            enrollment = self._create_course_enrollment(user, self.course_id)
            enrollment.is_active = is_active
            enrollment.save()

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    def test_run(self, mock_call_command, mock_send_mail, mock_log, get_course_by_id_mock):
        self._setup_certificate(self.course_id)
        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)

        get_course_by_id_mock.return_value = self._get_course_mock()

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            (u'修了証発行数： 3\n'
             u'※受講解除者0人を含みます（受講解除ユーザー名：）\n'
             u'---\n'
             u'修了判定データに含まれる\n'
             u'　* 合格かつ未アクティベート者数：0（未アクティベートユーザー名：）\n'
             u'　* 合格かつ退会者数：0（退会ユーザー名：）\n'
             u'\n'
             u'---\n{}').format(expected_urls_text),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))

    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
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
            'create_certs was completed. ({})'.format(self.course_id),
            u'2件の修了証を発行しました\n{}\n\n3件の修了証はまだ公開されていません\n{}'.format(
                expected_created_urls_text, expected_all_urls_text),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.warning.assert_called_once_with('User({}) was not found'.format(unknown_user.username))
        mock_log.exception.assert_not_called()

    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
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
            'create_certs was failure ({})'.format(self.course_id),
            'create_certs(create) was failed.\n\nFailure to generate the PDF files from create_certs command. ',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_called_once_with('Failure to generate the PDF files from create_certs command.')

    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
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
            'create_certs was failure ({})'.format(self.course_id),
            'create_certs(create) was failed.\n\nCaught the exception: Exception ',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_called_once_with('Caught the exception: Exception')

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('courseware.grades.grade', return_value={'percent': 0.9})
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(
        ((u'修了証発行数： 1\n'
          u'※受講解除者0人を含みます（受講解除ユーザー名：）\n'
          u'---\n'
          u'修了判定データに含まれる\n'
          u'　* 合格かつ未アクティベート者数：2（未アクティベートユーザー名：{}）\n'
          u'　* 合格かつ退会者数：0（退会ユーザー名：）\n'
          u'\n'
          u'---\n{}'), True, 2, -1)
    )
    @ddt.unpack
    def test_run_include_not_activate_and_course_passed(self, expect_email_body, is_course_passed,
                                                        not_activate_and_course_passed_count, create_cert_user_index,
                                                        mock_call_command, mock_send_mail, mock_log,
                                                        grades_grade_mock, get_course_by_id_mock):
        expect_user_list = []
        get_course_by_id_mock.return_value = self._get_course_mock()
        self._set_enroll(is_active=True)

        for i in range(not_activate_and_course_passed_count):
            user = self.users[i]
            user.is_active = False
            user.save()
            expect_user_list.append(user)

        created_cert_user = self.users[create_cert_user_index]
        self._create_certificate(
            self.course_id, 'generating', '{}-url'.format(created_cert_user.username), created_cert_user
        )

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '{}-url'.format(created_cert_user.username)
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            expect_email_body.format(
                ", ".join([u.username for u in expect_user_list if is_course_passed]),
                expected_urls_text
            ),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('courseware.grades.grade', return_value={'percent': 0.1})
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(
        ((u'修了証発行数： 1\n'
          u'※受講解除者0人を含みます（受講解除ユーザー名：）\n'
          u'---\n'
          u'修了判定データに含まれる\n'
          u'　* 合格かつ未アクティベート者数：0（未アクティベートユーザー名：{}）\n'
          u'　* 合格かつ退会者数：0（退会ユーザー名：）\n'
          u'\n'
          u'---\n{}'), False, 2, -1)
    )
    @ddt.unpack
    def test_run_include_not_activate_and_not_course_passed(self, expect_email_body, is_course_passed,
                                                            not_activate_and_course_passed_count, create_cert_user_index,
                                                            mock_call_command, mock_send_mail, mock_log,
                                                            grades_grade_mock, get_course_by_id_mock):
        expect_user_list = []
        get_course_by_id_mock.return_value = self._get_course_mock()
        self._set_enroll(is_active=True)

        for i in range(not_activate_and_course_passed_count):
            user = self.users[i]
            user.is_active = False
            user.save()
            expect_user_list.append(user)

        created_cert_user = self.users[create_cert_user_index]
        self._create_certificate(
            self.course_id, 'generating', '{}-url'.format(created_cert_user.username), created_cert_user
        )

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '{}-url'.format(created_cert_user.username)
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            expect_email_body.format(
                ", ".join([u.username for u in expect_user_list if is_course_passed]),
                expected_urls_text
            ),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('courseware.grades.grade', return_value={'percent': 0.9})
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(
        ((u'修了証発行数： 3\n'
          u'※受講解除者0人を含みます（受講解除ユーザー名：）\n'
          u'---\n'
          u'修了判定データに含まれる\n'
          u'　* 合格かつ未アクティベート者数：0（未アクティベートユーザー名：）\n'
          u'　* 合格かつ退会者数：2（退会ユーザー名：{}）\n'
          u'\n'
          u'---\n{}'), True, 2)
    )
    @ddt.unpack
    def test_run_include_disabled_account_and_course_passed(self, expect_email_body, is_course_passed,
                                                            disabled_account_count, mock_call_command, mock_send_mail,
                                                            mock_log, grades_grade_mock, get_course_by_id_mock):
        expect_user_list = []
        get_course_by_id_mock.return_value = self._get_course_mock()
        self._set_enroll(is_active=True)

        for i in range(disabled_account_count):
            user = self.users[i]
            self._create_user_standing(user, UserStanding.ACCOUNT_DISABLED)
            expect_user_list.append(user)

        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            expect_email_body.format(
                ", ".join([u.username for u in expect_user_list if is_course_passed]),
                expected_urls_text
            ),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('courseware.grades.grade', return_value={'percent': 0.1})
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(
        ((u'修了証発行数： 3\n'
          u'※受講解除者0人を含みます（受講解除ユーザー名：）\n'
          u'---\n'
          u'修了判定データに含まれる\n'
          u'　* 合格かつ未アクティベート者数：0（未アクティベートユーザー名：）\n'
          u'　* 合格かつ退会者数：0（退会ユーザー名：{}）\n'
          u'\n'
          u'---\n{}'), False, 2)
    )
    @ddt.unpack
    def test_run_include_disabled_account_and_not_course_passed(self, expect_email_body, is_course_passed,
                                                                disabled_account_count, mock_call_command, mock_send_mail,
                                                                mock_log, grades_grade_mock, get_course_by_id_mock):
        expect_user_list = []
        get_course_by_id_mock.return_value = self._get_course_mock()
        self._set_enroll(is_active=True)

        for i in range(disabled_account_count):
            user = self.users[i]
            self._create_user_standing(user, UserStanding.ACCOUNT_DISABLED)
            expect_user_list.append(user)

        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            expect_email_body.format(
                ", ".join([u.username for u in expect_user_list if is_course_passed]),
                expected_urls_text
            ),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('courseware.grades.grade', return_value={'percent': 0.9})
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(
        ((u'修了証発行数： 3\n'
          u'※受講解除者2人を含みます（受講解除ユーザー名：{}）\n'
          u'---\n'
          u'修了判定データに含まれる\n'
          u'　* 合格かつ未アクティベート者数：0（未アクティベートユーザー名：）\n'
          u'　* 合格かつ退会者数：0（退会ユーザー名：）\n'
          u'\n'
          u'---\n{}'), True)
    )
    @ddt.unpack
    def test_run_include_unenroll_student_and_course_passed(self, expect_email_body, is_course_passed,
                                                            mock_call_command, mock_send_mail, mock_log,
                                                            grades_grade_mock, get_course_by_id_mock):
        expect_user_list = []
        get_course_by_id_mock.return_value = self._get_course_mock()
        unenroll_student_count = 2

        for i in range(unenroll_student_count):
            enrollment = self._create_course_enrollment(self.users[i], self.course_id)
            enrollment.is_active = False
            enrollment.save()
            expect_user_list.append(enrollment)

        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            expect_email_body.format(
                ", ".join([e.user.username for e in expect_user_list if is_course_passed]),
                expected_urls_text
            ),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))

    @patch('ga_operation.tasks.get_course_by_id')
    @patch('courseware.grades.grade', return_value={'percent': 0.1})
    @patch('ga_operation.tasks.log')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    @ddt.data(
        ((u'修了証発行数： 3\n'
          u'※受講解除者0人を含みます（受講解除ユーザー名：{}）\n'
          u'---\n'
          u'修了判定データに含まれる\n'
          u'　* 合格かつ未アクティベート者数：0（未アクティベートユーザー名：）\n'
          u'　* 合格かつ退会者数：0（退会ユーザー名：）\n'
          u'\n'
          u'---\n{}'), False)
    )
    @ddt.unpack
    def test_run_include_unenroll_student_and_not_course_passed(self, expect_email_body, is_course_passed,
                                                                mock_call_command, mock_send_mail, mock_log,
                                                                grades_grade_mock, get_course_by_id_mock):
        expect_user_list = []
        unenroll_student_count = 2
        get_course_by_id_mock.return_value = self._get_course_mock()

        for i in range(unenroll_student_count):
            enrollment = self._create_course_enrollment(self.users[i], self.course_id)
            enrollment.is_active = False
            enrollment.save()
            expect_user_list.append(enrollment)

        for user in self.users:
            self._create_certificate(self.course_id, 'generating', '{}-url'.format(user.username), user)

        create_certs_task(self.course_id, 'test@example.com', [])

        mock_call_command.assert_called_once_with(
            'create_certs', 'create', self.course_id,
            username=False, debug=False, noop=False, prefix=''
        )
        expected_urls_text = '\n'.join(['{}-url'.format(user.username) for user in self.users])
        mock_send_mail.assert_called_once_with(
            'create_certs was completed. ({})'.format(self.course_id),
            expect_email_body.format(
                ", ".join([e.user.username for e in expect_user_list if is_course_passed]),
                expected_urls_text
            ),
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False
        )
        mock_log.exception.assert_not_called()
        get_course_by_id_mock.assert_called_once_with(course_key=CourseKey.from_string(self.course_id))


@ddt.ddt
@override_settings(GA_OPERATION_EMAIL_SENDER='sender@example.com')
class PublishCertsTest(TestCase):

    @staticmethod
    def _create_certificate(course_id, status, user=None):
        if user is None:
            user = UserFactory.create()
        course_key = CourseKey.from_string(course_id)
        return GeneratedCertificateFactory.create(user=user, course_id=course_key, status=status)

    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.call_command')
    @ddt.data([], ['user1', 'user2'])
    def test_success(self, student_ids, mock_call_command, mock_log, mock_send_mail):
        # Create certificate data
        for status, target_count, no_target_count in [
            ('deleted', 1, 2),
            ('deleting', 2, 3),
            ('downloadable', 3, 4),
            ('error', 4, 5),
            ('generating', 5, 6),
            ('notpassing', 6, 7),
            ('regenerating', 7, 8),
            ('restricted', 8, 9),
            ('unavailable', 9, 10),
        ]:
            for __ in range(target_count):
                self._create_certificate('course-v1:org+course+run', status)
            for __ in range(no_target_count):
                self._create_certificate('course-v1:org+courseX+run', status)

        publish_certs_task('course-v1:org+course+run', 'test@example.com', student_ids)

        if student_ids:
            self.assertEqual(mock_call_command.call_count, len(student_ids))
            for student_id in student_ids:
                mock_call_command.assert_any_call(
                    'create_certs', 'publish', 'course-v1:org+course+run',
                    username=student_id, debug=False, noop=False, prefix='', exclude=None
                )
        else:
            mock_call_command.assert_called_once_with(
                'create_certs', 'publish', 'course-v1:org+course+run',
                username=False, debug=False, noop=False, prefix='', exclude=None
            )
        status_counts = '\n'.join(student_ids) + '\n' if student_ids else ''
        status_counts += '\n\n--CertificateStatuses--\n\n' + '\n'.join([
            'deleted: 1',
            'deleting: 2',
            'downloadable: 3',
            'error: 4',
            'generating: 5',
            'notpassing: 6',
            'regenerating: 7',
            'restricted: 8',
            'unavailable: 9',
        ]) + '\n'
        mock_send_mail.assert_called_once_with(
            'create_certs(publish) has succeeded. (course-v1:org+course+run)',
            status_counts,
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False,
        )

    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.log')
    @patch('ga_operation.tasks.call_command')
    def test_success_with_wrong_user(self, mock_call_command, mock_log, mock_send_mail):
        student_ids = ['user1', 'user2', 'user3']
        mock_call_command.side_effect = [None, CertPDFUserNotFoundException, None]

        publish_certs_task('course-v1:org+course+run', 'test@example.com', student_ids)

        self.assertEqual(mock_call_command.call_count, len(student_ids))
        for student_id in student_ids:
            mock_call_command.assert_any_call(
                'create_certs', 'publish', 'course-v1:org+course+run',
                username=student_id, debug=False, noop=False, prefix='', exclude=None
            )

        status_counts = 'user1\nUser(user2) was not found\nuser3\n\n\n--CertificateStatuses--\n\n' + '\n'.join([
            'deleted: 0',
            'deleting: 0',
            'downloadable: 0',
            'error: 0',
            'generating: 0',
            'notpassing: 0',
            'regenerating: 0',
            'restricted: 0',
            'unavailable: 0',
        ]) + '\n'
        mock_log.warning.assert_any_call('User(user2) was not found\n')
        mock_send_mail.assert_called_once_with(
            'create_certs(publish) has succeeded. (course-v1:org+course+run)',
            status_counts,
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False,
        )

    @patch('ga_operation.tasks.traceback.format_exc', return_value='dummy_traceback')
    @patch('openedx.core.djangoapps.ga_operation.task_base.send_mail')
    @patch('ga_operation.tasks.call_command')
    def test_error(self, mock_call_command, mock_send_mail, mock_traceback):
        mock_call_command.side_effect = Exception('error')

        publish_certs_task('course-v1:org+course+run', 'test@example.com', [])

        mock_send_mail.assert_called_once_with(
            'create_certs(publish) has failed. (course-v1:org+course+run)',
            'create_certs(publish) has failed.\n\nCaught the exception: Exception\ndummy_traceback',
            'sender@example.com',
            ['test@example.com'],
            fail_silently=False,
        )
