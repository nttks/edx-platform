# -*- coding: utf-8 -*-
"""
End-to-end tests for survey of biz feature
"""
import csv
import os
import shutil
from unittest import skip

import bok_choy
from bok_choy.web_app_test import WebAppTest
from nose.plugins.attrib import attr

from common.test.acceptance.pages.biz.ga_contract import BizContractPage
from common.test.acceptance.pages.biz.ga_navigation import BizNavPage
from common.test.acceptance.pages.lms.courseware import CoursewarePage
from common.test.acceptance.pages.lms.course_nav import CourseNavPage
from common.test.acceptance.pages.lms.ga_instructor_dashboard import InstructorDashboardPage
from common.test.acceptance.pages.lms.ga_survey import SurveyPage
from common.test.acceptance.tests.biz import PLATFORMER_USER_INFO, \
    GaccoBizTestMixin, A_DIRECTOR_USER_INFO, A_COMPANY, SUPER_USER_INFO
from ..helpers import load_data_str
from ...fixtures.course import CourseFixture, XBlockFixtureDesc

DOWNLOAD_DIR = '/tmp'


@skip("Until apply security patch")
@attr('shard_ga_biz_1')
class BizSurveyTest(WebAppTest, GaccoBizTestMixin):
    """
    Tests that the survey functionality of biz works
    """

    def setUp(self):
        super(BizSurveyTest, self).setUp()
        # Install course
        self.course = CourseFixture('plat', self._testMethodName, 'biz_test_run', 'Biz Course ' + self._testMethodName)
        self.course.add_children(
                XBlockFixtureDesc('chapter', 'Test Section').add_children(
                        XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                                XBlockFixtureDesc('vertical', 'Test Unit').add_children(
                                        XBlockFixtureDesc('html', 'Test HTML', data=load_data_str('ga_survey.html'))
                                )
                        )
                )
        ).install()

        # Register a contract for A company
        self.switch_to_user(PLATFORMER_USER_INFO)
        self.contract = self.create_contract(BizContractPage(self.browser).visit(), 'PF', '2016/01/01',
                                             '2100/01/01', contractor_organization=A_COMPANY,
                                             detail_info=[self.course._course_key], additional_info=[u'部署'])

        # Change login user and answer survey
        acom_employees = [self.register_user(), self.register_user()]
        self.answers = [
            ['1', '2', 'yes', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[0]['username']),
             acom_employees[0]['username']],
            ['2', '1', 'no', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[1]['username']),
             acom_employees[1]['username']]
        ]
        self._answer_survey(acom_employees[0], self.answers[0])
        self._answer_survey(acom_employees[1], self.answers[1])

    def test_survey_as_director(self):
        """
        Tests that director of contractor can download survey.
        """
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'],
                                                     self.course._course_key).click_survey().click_download_button()
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_as_director__1')
        self._verify_csv_answers(self.answers)

    def test_survey_as_staff(self):
        """
        Tests that staff of platfomer can download survey.
        """
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        survey_page_section.click_download_button()
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_as_staff__1')
        self._verify_csv_answers(self.answers)

    def _answer_survey(self, login_user, answer):
        """
        Answer survey
        """
        # Register invitation as manager of A company
        self.switch_to_user(login_user)
        self.register_invitation(self.contract['Invitation Code'], ['Marketing'])

        # Visit survey pageｘ
        CoursewarePage(self.browser, self.course._course_key).visit()
        CourseNavPage(self.browser).go_to_section('Test Section', 'Test Subsection')
        survey_page = SurveyPage(self.browser).wait_for_page()
        self.assertTrue(survey_page.is_submit_button_enabled())

        # Submit
        survey_page.fill_item('Q1', answer[0])
        survey_page.fill_item('Q2', answer[1])
        survey_page.fill_item('Q3', answer[2])
        survey_page.fill_item('Q4', answer[3])
        survey_page.submit()

        # Verify message
        self.assertIn(u"ご回答ありがとうございました。", survey_page.wait_for_messages())
        self.assertFalse(survey_page.is_submit_button_enabled())

    def _verify_csv_answers(self, expect_data):
        """
        Verify csv file.
        """
        # Get csv file
        tmp_file = max(
                [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.count('.csv')],
                key=os.path.getctime)
        csv_file = os.path.join(os.environ.get('SELENIUM_DRIVER_LOG_DIR', ''), self._testMethodName + '.csv')
        shutil.move(os.path.join(DOWNLOAD_DIR, tmp_file), csv_file)
        # Read csv
        reader = csv.DictReader(open(csv_file))
        csv_data = [[row.get('Q1').decode('utf8'), row.get('Q2').decode('utf8'), row.get('Q3').decode('utf8'),
                     row.get('Q4').decode('utf8'), row.get('User Name').decode('utf8')] for row in reader]

        self.assertEqual(csv_data, expect_data)
