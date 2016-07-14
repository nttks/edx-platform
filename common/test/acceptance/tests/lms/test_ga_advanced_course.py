# -*- coding: utf-8 -*-
"""
tests for advanced course
"""
from unittest import skip

from bok_choy.web_app_test import WebAppTest

from ...fixtures.course import CourseFixture
from ...pages.common.logout import LogoutPage
from ...pages.lms.auto_auth import AutoAuthPage
from lms.envs.bok_choy import EMAIL_FILE_PATH

from ..ga_helpers import GaccoTestMixin
from ...pages.lms.ga_advanced_course import (
    AdvancedCourseChoosePage, AdvancedF2FCoursesPage, CourseAboutPage, DashboardPage,
)


class AdvancedCourseTest(WebAppTest, GaccoTestMixin):

    COURSE_ORG = 'test_advanced_course_org'
    COURSE_RUN = 'test_run'
    COURSE_DISPLAY = 'Test Course with Advanced'

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(AdvancedCourseTest, self).setUp()

        course = CourseFixture(
            self.COURSE_ORG, self._testMethodName,
            self.COURSE_RUN, self.COURSE_DISPLAY,
            settings={
                'is_f2f_course': {'value': True},
                'is_f2f_course_sell': {'value': True},
            }
        ).install()

        self.course_id = course._course_key

        # Set up email client
        self.setup_email_client(EMAIL_FILE_PATH)

        # Set window size
        self.setup_window_size_for_pc()

    def _auto_auth(self, course_id=None):
        return AutoAuthPage(self.browser, course_id=course_id).visit().user_info

    def _logout(self):
        LogoutPage(self.browser).visit()

    def _assert_purchase_email(self, ticket_name, price, payment_method):
        email_message = self.email_client.get_latest_message()
        self.assertEqual(email_message['subject'], u'【gacco】チケットご購入完了のお知らせ')
        self.assertIn(ticket_name, email_message['body'])
        self.assertIn('{:,d}'.format(price), email_message['body'])
        self.assertIn(payment_method, email_message['body'])

    def _assert_course_name_and_button(self, courses_page, course_name, btn_text='Subscribe', exists=True):
        if exists:
            self.assertTrue(courses_page.check_course_name(course_name))
            self.assertTrue(courses_page.check_course_button(course_name, btn_text))
        else:
            self.assertFalse(courses_page.check_course_name(course_name))

    def _assert_course_detail(
        self, courses_page, course_name, start_date=None, start_time=None, end_time=None, description=None,
        place_name=None, ticket_names=[], place_link=None, place_address=None, place_access=None, other_content=None
    ):
        content = courses_page.get_course_content(course_name)
        self.assertEqual(description, content['description'])
        self.assertEqual(start_date, content['start_date'])
        self.assertEqual(start_time, content['start_time'])
        self.assertEqual(end_time, content['end_time'])
        self.assertEqual(place_name, content['place_name'])
        self.assertEqual(len(ticket_names), len(content['tickets']))
        for i, ticket_name in enumerate(ticket_names):
            self.assertTrue(content['tickets'][i].startswith(ticket_name))
        self.assertEqual(place_link, content['place_link'])
        self.assertEqual(place_address, content['place_address'])
        self.assertEqual(place_access, content['place_access'])
        if other_content:
            self.assertEqual(other_content, content['other_content'])
        else:
            self.assertIsNone(content['other_content'])

    def _assert_ticket(self, ticket_page, ticket_name, description='', price=0, available=True, exists=True):
        if exists:
            self.assertTrue(ticket_page.check_ticket_name(ticket_name))
            content = ticket_page.get_ticket_content(ticket_name)
            self.assertEqual(description, content['description'])
            if available:
                self.assertEqual('{:,d}'.format(price), content['price'])
            else:
                self.assertTrue(content['is_end_of_sale'])
        else:
            self.assertFalse(ticket_page.check_ticket_name(ticket_name))

    def _assert_receipt(
        self, receipt_page, course_name, advanced_course_name, ticket_name,
        start_date, start_time, end_time, place_name, price, payment_method
    ):
        content = receipt_page.get_receipt_content()
        self.assertTrue(content['course_name'].startswith(course_name))
        self.assertIn(advanced_course_name, content['course_name'])
        self.assertTrue(content['course_name'].endswith(ticket_name))
        self.assertEqual('{} {} - {}'.format(start_date, start_time, end_time), content['openning_time'])
        self.assertEqual(place_name, content['place_name'])
        self.assertEqual('{:,d}'.format(price), content['price'])
        self.assertEqual(payment_method, content['payment_method'])

    @skip("Until fix dashboard")
    def test_purchase_flow_when_enroll(self):
        """
        Scenario:
        After enroll, and ticket purchase as it is.

        1. Visit course about page and enroll
        2. Show advanced course choose and click view-detail button
        3. Show advanced course list page and select one of these
        4. Show advanced course ticket option page and purchase (use fake_processor)
        5. Show advanced course receipt page and go to dashboard
        6. Show dashboard and visit receipt page
        7. Logout and logged-in by another user
        8. Show advanced course list page and check course full
        """

        # Initialize (not enroll)
        self._auto_auth()

        # Visit course about page and enroll
        course_about_page = CourseAboutPage(self.browser, self.course_id).visit()
        choose_page = course_about_page.enroll()

        # Verify choose page has two track
        self.assertTrue(choose_page.has_face_to_face_track())
        self.assertTrue(choose_page.has_online_track())

        f2f_courses_page = choose_page.show_face_to_face_courses_page()

        # Verify advanced course list page
        self.assertFalse(f2f_courses_page.get_error_message())
        ## Verify three advanced course exists and check button status
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 1')
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 2')
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 3', 'End of sale')
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 4', exists=False)

        ## Vefify toggle area
        self.assertFalse(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 1'))
        self.assertFalse(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 2'))
        ### open course 1
        f2f_courses_page.toggle_show_more('Test Advance Course 1')
        self.assertTrue(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 1'))
        self._assert_course_detail(
            f2f_courses_page, 'Test Advance Course 1',
            start_date='2026/01/01 (Thu)', start_time='11:11', end_time='22:22',
            description='test advanced course description 1',
            place_name='test place 1', place_link='http://example1.com/',
            place_address='test address 1', place_access='test access 1',
            ticket_names=['test ticket name 1', 'test ticket name 2'], other_content='content 1'
        )
        self.assertFalse(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 2'))
        ### open course 2
        f2f_courses_page.toggle_show_more('Test Advance Course 2')
        self.assertTrue(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 1'))
        self.assertTrue(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 2'))
        self._assert_course_detail(
            f2f_courses_page, 'Test Advance Course 2',
            start_date='2026/01/02 (Fri)', start_time='11:12', end_time='22:23',
            description='test advanced course description 2',
            place_name='test place 2', place_link='http://example2.com/',
            place_address='test address 2', place_access='test access 2',
            ticket_names=['test ticket name 3']
        )
        ### close course 1
        f2f_courses_page.toggle_show_more('Test Advance Course 1')
        self.assertFalse(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 1'))
        self.assertTrue(f2f_courses_page.is_displayed_toggle_area('Test Advance Course 2'))

        ## subscribe
        choose_ticket_page = f2f_courses_page.subscribe_by_summary('Test Advance Course 1')

        # Verify ticket page
        self._assert_ticket(choose_ticket_page, 'test ticket name 1', 'ticket description 1', 1080)
        self._assert_ticket(choose_ticket_page, 'test ticket name 2', 'ticket description 2', available=False)
        self._assert_ticket(choose_ticket_page, 'test ticket name 3', exists=False)
        ## choose ticket
        payment_page = choose_ticket_page.purchase('test ticket name 1')

        # submit on fake-payment page
        receipt_page = payment_page.submit_payment('card')
        self._assert_receipt(
            receipt_page, self.COURSE_DISPLAY, 'Test Advance Course 1', 'test ticket name 1',
            '2026/01/01 (Thu)', '11:11', '22:22', 'test place 1', 1080, 'Credit Card'
        )

        self._assert_purchase_email('Test Advance Course 1 test ticket name 1', 1080, 'Credit Card')

        dashboard_page = receipt_page.show_dashboard_page()

        # Verify not shown upsell message on the dashboard
        self.assertFalse(dashboard_page.has_advanced_course_upsell_message(self.COURSE_DISPLAY))

        # Verify receipt page
        dashboard_page.show_receipt_page(self.COURSE_DISPLAY)

        #f2f_courses_page = receipt_page.show_courses_page()
        f2f_courses_page.visit()

        ## Verify two advanced course exists and one of those is purchased
        ## Although capacity this course is sold out for one person, it has been purchased is priority
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 1', 'Purchased')
        ## Other course is still available
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 2')

        # Logout and logged-in by another user
        self._logout()
        self._auto_auth(self.course_id)
        f2f_courses_page = AdvancedF2FCoursesPage(self.browser, self.course_id).visit()

        # Verify course 1 is full
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 1', 'Sold out')
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 2')
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 3', 'End of sale')
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 4', exists=False)

    @skip("Until fix dashboard")
    def test_purchase_flow_from_dashboard(self):
        """
        Scenario:
        Course has only one advanced course.

        1. Visit dashboard and go to list page
        2. Show advanced course list page and go to ticket option page
        3. Show advanced course ticket option page and purchase (use fake_processor)
        4. Show advanced course receipt page and go to dashboard
        """
        # Initialize (enroll)
        self._auto_auth(self.course_id)

        # Visit dashboard page
        dashboard_page = DashboardPage(self.browser).visit()
        ## Verify show advanced course message and no order history
        self.assertTrue(dashboard_page.has_advanced_course_upsell_message(self.COURSE_DISPLAY))
        self.assertFalse(dashboard_page.has_advanced_course_purchased_message(self.COURSE_DISPLAY))
        ## Verify refund info is not shown
        dashboard_page.show_unenroll_settings(self.COURSE_DISPLAY)
        self.assertEqual(u"", dashboard_page.get_refund_info_message())
        dashboard_page.close_unenroll_modal()

        ## click button in upsell message
        f2f_courses_page = dashboard_page.show_advanced_courses_page(self.COURSE_DISPLAY)

        # Verify advanced course list page is shown
        self.assertFalse(f2f_courses_page.get_error_message())
        ## Verify advanced course exists
        self._assert_course_name_and_button(f2f_courses_page, 'Test Advance Course 11')
        ## click subscribe
        choose_ticket_page = f2f_courses_page.subscribe_by_detail('Test Advance Course 11')

        # Verify ticket option page is shown
        payment_page = choose_ticket_page.purchase('test ticket name 11')

        # submit on fake-payment page
        receipt_page = payment_page.submit_payment('docomo')
        self._assert_receipt(
            receipt_page, self.COURSE_DISPLAY, 'Test Advance Course 11', 'test ticket name 11',
            '2026/01/01 (Thu)', '00:00', '12:00', 'test place 11', 4320, 'Docomo Mobile Payment'
        )

        self._assert_purchase_email('Test Advance Course 11 test ticket name 11', 4320, 'Docomo Mobile Payment')

        dashboard_page = receipt_page.show_dashboard_page()

        # Verify not shown face-to-face message on the dashboard
        self.assertFalse(dashboard_page.has_advanced_course_upsell_message(self.COURSE_DISPLAY))

        # Verify refund info is shown
        dashboard_page.show_unenroll_settings(self.COURSE_DISPLAY)
        self.assertEqual(
            u"If you unenroll, ticket, such as face-to-face classroom you have purchased will not be canceled. Please contact us through the Help If you would like to cancel the ticket.",
            dashboard_page.get_refund_info_message()
        )

    def test_not_logged_in_and_register(self):
        """
        Scenario:
        To enroll in not logged-in state.

        1. Visit course about page and enroll
        2. Show register page and register
        3. Show advanced course choose page
        """
        course_about_page = CourseAboutPage(self.browser, self.course_id).visit()
        register_page = course_about_page.enroll(login=False)

        username = self.unique_id[0:6]
        register_page.register(
            email='{}@example.com'.format(username), password='abcdefG1', username=username,
            full_name=username, terms_of_service=True
        )

        # Verify course choose page is shown
        AdvancedCourseChoosePage(self.browser, self.course_id).wait_for_page()

    def test_not_logged_in_and_register_with_not_advanced_course(self):
        """
        Scenario:
        Course has not advanced course.
        To enroll in not logged-in state.

        1. Visit course about page and enroll
        2. Show register page and register
        3. Show dashboard page
        """
        _course_id = CourseFixture(
            self.COURSE_ORG, '{}_2'.format(self._testMethodName), self.COURSE_RUN, self.COURSE_DISPLAY
        ).install()._course_key

        course_about_page = CourseAboutPage(self.browser, _course_id).visit()
        register_page = course_about_page.enroll(login=False)

        username = self.unique_id[0:6]
        register_page.register(
            email='{}@example.com'.format(username), password='abcdefG1', username=username,
            full_name=username, terms_of_service=True
        )

        # Verify dashboard page is shown
        DashboardPage(self.browser).wait_for_page()

    def test_not_logged_in_and_login(self):
        """
        Scenario:
        To enroll in not logged-in state.

        1. Visit course about page and enroll
        2. Show register page
        3. Toggle form and login
        4. Show advanced course choose page
        """
        # Create user and logout
        user = self._auto_auth()
        self._logout()

        course_about_page = CourseAboutPage(self.browser, self.course_id).visit()
        register_page = course_about_page.enroll(login=False)

        register_page.toggle_form()
        register_page.login(email=user['email'], password=user['username'])

        # Verify course choose page is shown
        AdvancedCourseChoosePage(self.browser, self.course_id).wait_for_page()

    def test_not_logged_in_and_login_with_not_advanced_course(self):
        """
        Scenario:
        Course has not advanced course.
        To enroll in not logged-in state.

        1. Visit course about page and enroll
        2. Show register page
        3. Toggle form and login
        4. Show dashboard page
        """
        # Create user and logout
        user = self._auto_auth()
        self._logout()

        _course_id = CourseFixture(
            self.COURSE_ORG, '{}_2'.format(self._testMethodName), self.COURSE_RUN, self.COURSE_DISPLAY
        ).install()._course_key

        course_about_page = CourseAboutPage(self.browser, _course_id).visit()
        register_page = course_about_page.enroll(login=False)

        register_page.toggle_form()
        register_page.login(email=user['email'], password=user['username'])

        # Verify dashboard page is shown
        DashboardPage(self.browser).wait_for_page()
