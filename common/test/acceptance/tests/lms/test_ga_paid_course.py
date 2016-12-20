
from ..helpers import UniqueCourseTest
from ...fixtures.course import CourseFixture
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.create_mode import ModeCreationPage
from lms.envs.bok_choy import EMAIL_FILE_PATH

from ..ga_helpers import GaccoTestMixin
from ...pages.lms.ga_pay_and_verify import CourseAboutPage


class PaidCourseTest(UniqueCourseTest, GaccoTestMixin):

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(PaidCourseTest, self).setUp()

        CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name']
        ).install()

        # Add a no-id-professional mode to the course
        ModeCreationPage(
            self.browser,
            self.course_id,
            mode_slug=u'no-id-professional',
            mode_display_name=u'Paid Course',
            min_price=100
        ).visit()

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Set window size
        self.setup_window_size_for_pc()

    def _auto_auth(self, course_id=None):
        return AutoAuthPage(self.browser, course_id=course_id).visit().user_info

    def _assert_receipt_content(self, receipt_content, display_name, payment_method, price):
        self.assertEqual(self.course_info['display_name'], receipt_content['description'])
        self.assertEqual(payment_method, receipt_content['payment_method'])
        self.assertEqual(price, receipt_content['price'])

    def _assert_purchase_email(self, display_name, price, payment_method):
        email_message = self.email_client.get_latest_message()
        self.assertEqual(email_message['subject'], 'Your course has been completed from edX')
        self.assertIn(display_name, email_message['body'])
        self.assertIn('{:,d}'.format(price), email_message['body'])
        self.assertIn(payment_method, email_message['body'])

    def test_enroll_paid_course_flow(self):
        self._auto_auth()

        about_page = CourseAboutPage(self.browser, self.course_id).visit()
        payment_flow = about_page.register()

        payment_data = payment_flow.get_payment_content()
        self.assertEqual(self.course_info['display_name'], payment_data['description'])
        # price 100 and tax 8
        self.assertEqual('108', payment_data['price'])

        fake_payment_page = payment_flow.proceed_to_payment()
        fake_payment_page.submit_payment()

        self._assert_receipt_content(
            payment_flow.get_receipt_content(),
            self.course_info['display_name'], 'Credit Card', '108',
        )
        self._assert_purchase_email(self.course_info['display_name'], 108, 'Credit Card')

        dashboard_page = payment_flow.go_to_dashboard()
        self.assertTrue(dashboard_page.has_paid_course_purchased_message(self.course_info['display_name']))

        dashboard_page.show_receipt_page(self.course_id, self.course_info['display_name'])
        self._assert_receipt_content(
            payment_flow.get_receipt_content(),
            self.course_info['display_name'], 'Credit Card', '108',
        )
