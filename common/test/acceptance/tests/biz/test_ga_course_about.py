# -*- coding: utf-8 -*-
"""
End-to-end tests for course about of biz feature
"""
import datetime

import requests
from bok_choy.web_app_test import WebAppTest
from nose.plugins.attrib import attr

from common.test.acceptance.fixtures.course import CourseFixture
from common.test.acceptance.pages.biz.ga_contract import BizContractPage
from common.test.acceptance.pages.biz.ga_course_about import CourseAboutPage
from common.test.acceptance.pages.biz.ga_invitation import BizInvitationPage, BizInvitationConfirmPage
from common.test.acceptance.pages.common.logout import LogoutPage
from common.test.acceptance.pages.lms.ga_dashboard import DashboardPage
from common.test.acceptance.pages.lms.ga_instructor_dashboard import MembershipPageMemberListSection, \
    InstructorDashboardPage
from common.test.acceptance.tests.biz import PLATFORMER_USER_INFO, \
    A_COMPANY, A_MANAGER_USER_INFO, SUPER_USER_INFO, GaccoBizTestMixin, A_DIRECTOR_USER_INFO


@attr('shard_ga_biz_1')
class BizCourseAboutTest(WebAppTest, GaccoBizTestMixin):
    """
    Tests that the course about functionality works
    """
    CONTRACT_TYPE_PF = 'PF'

    def test_opening_course(self):
        """
        Tests the course is opening.
        """
        # Create a platfomer service courses
        course = CourseFixture('plat', self._testMethodName, 'biz_test_run',
                               'Biz Test Course ' + self._testMethodName)
        course.install()

        # Register a contract with platfomer
        self.switch_to_user(PLATFORMER_USER_INFO)
        contract = self.create_contract(BizContractPage(self.browser).visit(),
                                        self.CONTRACT_TYPE_PF, '2016/01/01', '2100/01/01',
                                        contractor_organization=A_COMPANY,
                                        detail_info=[course._course_key], additional_info=[u'部署'])
        invitation_code = contract['Invitation Code']

        # Logout
        LogoutPage(self.browser).visit()

        # Case 65
        # Non login
        course_about_url = CourseAboutPage(self.browser, course._course_key).url
        self.browser.get(course_about_url)
        self.assertEqual(requests.get(course_about_url).status_code, 404)

        # Case 66
        # Login as manager of A company
        self.switch_to_user(A_MANAGER_USER_INFO)
        self.browser.get(course_about_url)
        self.assertEqual(requests.get(course_about_url).status_code, 404)

        # Case 67
        # Register invitation code
        BizInvitationPage(self.browser).visit().input_invitation_code(invitation_code).click_register_button()
        BizInvitationConfirmPage(self.browser, invitation_code).wait_for_page()
        CourseAboutPage(self.browser, course._course_key).visit()

        # Case 68
        # Register invitation code and additional info
        BizInvitationPage(self.browser).visit().input_invitation_code(invitation_code).click_register_button()
        BizInvitationConfirmPage(self.browser, invitation_code).wait_for_page().input_additional_info(u'マーケティング部', 0) \
            .click_register_button()
        DashboardPage(self.browser).wait_for_page()
        CourseAboutPage(self.browser, course._course_key).visit()

    def test_wait_start_course(self):
        """
        Tests the course wait to start.
        """
        # Create a platfomer service courses
        now_date = datetime.datetime.now()
        start_date = now_date + datetime.timedelta(days=1)
        course = CourseFixture('plat', self._testMethodName, 'biz_test_run',
                               'Biz Test Course ' + self._testMethodName, start_date=start_date)
        course.install()

        # Register a contract with platfomer
        self.switch_to_user(PLATFORMER_USER_INFO)
        self.create_contract(BizContractPage(self.browser).visit(), self.CONTRACT_TYPE_PF, '2016/01/01', '2100/01/01',
                             contractor_organization=A_COMPANY, detail_info=[course._course_key],
                             additional_info=[u'部署'])

        # Case 70
        # Login with gacco staff
        self.switch_to_user(SUPER_USER_INFO)
        CourseAboutPage(self.browser, course._course_key).visit()

        # Case 71
        # Add course staff role for A company director
        self._add_course_role(course._course_key, A_DIRECTOR_USER_INFO['email'])
        # Login as A company course staff
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        CourseAboutPage(self.browser, course._course_key).visit()

    def test_closed_course(self):
        """
        Tests the course is closed.
        """
        # Create platfomer service courses
        now_date = datetime.datetime.now()
        end_date = now_date + datetime.timedelta(days=-1)
        course = CourseFixture('plat', self._testMethodName, 'biz_test_run',
                               'Biz Test Course ' + self._testMethodName, end_date=end_date)
        course.install()

        # Register a contract with platfomer
        self.switch_to_user(PLATFORMER_USER_INFO)
        self.create_contract(BizContractPage(self.browser).visit(), self.CONTRACT_TYPE_PF, '2016/01/01', '2100/01/01',
                             contractor_organization=A_COMPANY, detail_info=[course._course_key],
                             additional_info=[u'部署'])

        # Case 72
        # Add course staff role for A company director
        self._add_course_role(course._course_key, A_DIRECTOR_USER_INFO['email'])
        # Login as A company course staff
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        CourseAboutPage(self.browser, course._course_key).visit()

    def _add_course_role(self, course_id, email, role_name='staff'):
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, course_id).visit()
        instructor_dashboard_page.select_membership()
        MembershipPageMemberListSection(self.browser).wait_for_page().add_role(role_name, email)
