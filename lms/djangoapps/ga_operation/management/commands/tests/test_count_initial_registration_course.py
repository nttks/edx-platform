import ddt
from datetime import datetime
from mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test.utils import override_settings

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.course_global.tests.factories import CourseGlobalSettingFactory
from student.tests.factories import CourseEnrollmentFactory, UserFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


@ddt.ddt
@override_settings(
    TIME_ZONE='Asia/Tokyo',
    GA_OPERATION_EMAIL_SENDER_REGISTRATION_COURSE_DAILY_REPORT='sender@example.com',
    GA_OPERATION_CALLBACK_EMAIL_REGISTRATION_COURSE_DAILY_REPORT=['receiver@example.com'],
)
class InitialRegistrationCourseCountTest(ModuleStoreTestCase):

    def setUp(self):
        super(InitialRegistrationCourseCountTest, self).setUp()

    @staticmethod
    def _setup_course_enrollment(course_id_dict, user_count):
        course_list = []
        for course_id, global_enabled in course_id_dict.iteritems():
            course_key = CourseKey.from_string(course_id)
            CourseGlobalSettingFactory.create(course_id=course_key, global_enabled=global_enabled)
            course_list.append(CourseFactory.create(org=course_key.org, course=course_key.course, run=course_key.run))
        for _ in range(user_count):
            for course in course_list:
                CourseEnrollmentFactory.create(user=UserFactory.create(), course_id=course.id)

    @patch('ga_operation.management.commands.count_initial_registration_course.datetime')
    @patch('ga_operation.management.commands.count_initial_registration_course.traceback.format_exc', return_value='dummy_traceback')
    @patch('ga_operation.management.commands.count_initial_registration_course.send_mail')
    @ddt.data(
        ({'gacco/ht001/2015_00': True}, 3, 0),
        ({'gacco/ht001/2015_00': True, 'gacco/course1/run': False}, 3, 3),
        ({'gacco/ht001/2015_00': True, 'other/course/run': False, 'gacco/course1/run': False}, 3, 3),
    )
    @ddt.unpack
    def test_handle(self, course_id_dict, user_count, expect_count, mock_send_mail, mock_traceback, mock_datetime):
        expect_datetime = datetime(2020, 7, 24)
        mock_datetime.now.return_value = expect_datetime
        self._setup_course_enrollment(course_id_dict, user_count)

        call_command('count_initial_registration_course')

        mock_traceback.assert_not_called_once()
        mock_send_mail.assert_called_once_with(
            'Initial registration course daily report ({0:%Y/%m/%d})'.format(expect_datetime),
            '"gacco/course1/run",{}'.format(expect_count) if expect_count else '',
            settings.GA_OPERATION_EMAIL_SENDER_REGISTRATION_COURSE_DAILY_REPORT,
            settings.GA_OPERATION_CALLBACK_EMAIL_REGISTRATION_COURSE_DAILY_REPORT,
            fail_silently=False,
        )

    @patch('ga_operation.management.commands.count_initial_registration_course.datetime')
    @patch('ga_operation.management.commands.count_initial_registration_course.traceback.format_exc', return_value='dummy_traceback')
    @patch('ga_operation.management.commands.count_initial_registration_course.send_mail')
    @patch('ga_operation.management.commands.count_initial_registration_course.connection')
    def test_handle_caught_exception(self, mock_connection, mock_send_mail, mock_traceback, mock_datetime):
        expect_datetime = datetime(2020, 7, 24)
        mock_datetime.now.return_value = expect_datetime
        mock_connection.cursor().__enter__().execute.side_effect = Exception()

        call_command('count_initial_registration_course')

        mock_traceback.assert_called_once()
        mock_send_mail.assert_called_once_with(
            'Initial registration course daily report ({0:%Y/%m/%d})'.format(expect_datetime),
            'dummy_traceback',
            settings.GA_OPERATION_EMAIL_SENDER_REGISTRATION_COURSE_DAILY_REPORT,
            settings.GA_OPERATION_CALLBACK_EMAIL_REGISTRATION_COURSE_DAILY_REPORT,
            fail_silently=False,
        )
