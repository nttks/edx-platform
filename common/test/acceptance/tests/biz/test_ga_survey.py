# -*- coding: utf-8 -*-
"""
End-to-end tests for survey of biz feature
"""
import codecs
import csv
import os
import shutil

from bok_choy.web_app_test import WebAppTest
from django.utils.crypto import get_random_string
from nose.plugins.attrib import attr

from common.test.acceptance.pages.biz.ga_contract import BizContractPage
from common.test.acceptance.pages.biz.ga_navigation import BizNavPage
from common.test.acceptance.pages.lms.courseware import CoursewarePage
from common.test.acceptance.pages.lms.course_nav import CourseNavPage
from common.test.acceptance.pages.lms.ga_instructor_dashboard import InstructorDashboardPage
from common.test.acceptance.pages.lms.ga_survey import SurveyPage
from common.test.acceptance.tests.biz import PLATFORMER_USER_INFO, \
    GaccoBizTestMixin, A_DIRECTOR_USER_INFO, A_COMPANY, A_COMPANY_NAME, SUPER_USER_INFO
from ..helpers import load_data_str
from ...fixtures.course import CourseFixture, XBlockFixtureDesc
from ...pages.lms.ga_django_admin import DjangoAdminPage

DOWNLOAD_DIR = '/tmp'


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
                                             detail_info=[self.course._course_key])

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
        BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'], self.course._course_key)\
            .click_survey().check_encoding_utf8(False).click_download_button()
        self._verify_csv_answers(self.answers, 'utf16')

    def test_survey_as_director_utf8(self):
        """
        Tests that director of contractor can download survey.
        """
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'], self.course._course_key)\
            .click_survey().check_encoding_utf8(True).click_download_button()
        self._verify_csv_answers(self.answers, 'utf8')

    def test_survey_as_staff(self):
        """
        Tests that staff of platfomer can download survey.
        """
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        survey_page_section.check_encoding_utf8(False).click_download_button()
        self._verify_csv_answers(self.answers, 'utf16')

    def test_survey_as_staff_utf8(self):
        """
        Tests that staff of platfomer can download survey.
        """
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        survey_page_section.check_encoding_utf8(True).click_download_button()
        self._verify_csv_answers(self.answers, 'utf8')

    def test_utf8_checkbox_is_saved_as_biz(self):
        """
        Test that the value of the checkbox is saved as biz.
        """
        # checked
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        bizSurveyPage = BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'],
                                                                     self.course._course_key).click_survey()
        bizSurveyPage.check_encoding_utf8(True).click_download_button()
        bizSurveyPage = BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'], 
                                                                     self.course._course_key).click_survey()
        self.assertTrue(bizSurveyPage.is_encoding_utf8_selected())
        # unchecked
        bizSurveyPage.check_encoding_utf8(False).click_download_button()
        bizSurveyPage = BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'],
                                                                     self.course._course_key).click_survey()
        self.assertFalse(bizSurveyPage.is_encoding_utf8_selected())

    def test_utf8_checkbox_is_saved_as_instructor(self):
        """
        Test that the value of the checkbox is saved as instructor.
        """
        # checked
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        survey_page_section.check_encoding_utf8(True).click_download_button()
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        self.assertTrue(survey_page_section.is_encoding_utf8_selected())
        # unchecked
        survey_page_section.check_encoding_utf8(False).click_download_button()
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        self.assertFalse(survey_page_section.is_encoding_utf8_selected())

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

    def _verify_csv_answers(self, expect_data, encoding):
        """
        Verify csv file.
        """
        # Get csv file. (Content_type is 'text/tab-separated-values')
        tmp_file = max(
                [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.count('.tsv')],
                key=os.path.getctime)
        csv_file = os.path.join(os.environ.get('SELENIUM_DRIVER_LOG_DIR', ''), self._testMethodName + '.csv')
        shutil.move(os.path.join(DOWNLOAD_DIR, tmp_file), csv_file)
        # Read csv
        with codecs.open(csv_file, encoding=encoding) as f:
            reader = csv.DictReader([row.encode('utf8') for row in f], delimiter="\t")
        csv_data = [[row.get('Q1').decode('utf8'), row.get('Q2').decode('utf8'), row.get('Q3').decode('utf8'),
                     row.get('Q4').decode('utf8'), row.get('User Name').decode('utf8')] for row in reader]
        self.assertEqual(csv_data, expect_data)


class LoginCodeEnabledBizSurveyTest(WebAppTest, GaccoBizTestMixin):
    """
    Tests that the login code enabled survey functionality of biz works
    """

    def _make_students_auth(self, user_info_list):
        return '\r\n'.join([
            '{},{},{},{},{}'.format(
                user_info['email'],
                user_info['username'],
                user_info['fullname'] if 'fullname' in user_info else 'Full Name',
                user_info['login_code'] if 'login_code' in user_info else user_info['username'],
                user_info['password']
            )
            for user_info in user_info_list
        ])

    def setUp(self):
        super(LoginCodeEnabledBizSurveyTest, self).setUp()
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
                                             detail_info=[self.course._course_key])

        # Make contract auth
        self.django_admin_page = DjangoAdminPage(self.browser)
        self.new_url_code = get_random_string(8)
        self.switch_to_user(SUPER_USER_INFO)
        django_admin_add_page = self.django_admin_page.visit().click_add('ga_contract', 'contractauth')
        django_admin_list_page = django_admin_add_page.input({
            'contract': self.contract['Contract Name'],
            'url_code': self.new_url_code,
            'send_mail': True,
        }).save()

        # Register user as director
        self.new_director = self.register_user(course_id=self.course._course_key)
        self.grant(PLATFORMER_USER_INFO,A_COMPANY_NAME, 'director', self.new_director)

        # Make acom employees
        acom_employees = [self.new_user_info for _ in range(2)]
        for acom_employee in acom_employees:
            acom_employee['login_code'] = 'logincode_' + get_random_string(8)
        self.switch_to_user(self.new_director)
        biz_register_students_page = BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'],
                                                     self.course._course_key).click_register_students()
        biz_register_students_page.input_students(
            self._make_students_auth(acom_employees)).click_register_button().click_popup_yes()
        biz_register_students_page.wait_for_message(
            u'Began the processing of Student Register.Execution status, please check from the task history.'
        )

        # Change login user and answer survey
        self.answers = [
            ['1', '2', 'yes', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[0]['username']),
             acom_employees[0]['username']],
            ['2', '1', 'no', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[1]['username']),
             acom_employees[1]['username']]
        ]
        self._answer_survey(acom_employees[0], self.answers[0])
        self._answer_survey(acom_employees[1], self.answers[1])

        # Make expect datas of survey csv
        self.expect_datas_as_director = [
            [acom_employees[0]['login_code'], '1', '2', 'yes', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[0]['username']),
             acom_employees[0]['username']],
            [acom_employees[1]['login_code'], '2', '1', 'no', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[1]['username']),
             acom_employees[1]['username']]
        ]

        self.expect_datas_as_staff = [
            ['1', '2', 'yes', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[0]['username']),
             acom_employees[0]['username']],
            ['2', '1', 'no', u'意見 by {}_{}'.format(self._testMethodName, acom_employees[1]['username']),
             acom_employees[1]['username']]
        ]

    def test_survey_as_director(self):
        """
        Tests that director of contractor can download survey.
        """
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'], self.course._course_key)\
            .click_survey().check_encoding_utf8(False).click_download_button()
        self._verify_csv_answers(self.expect_datas_as_director, True, 'utf16')

    def test_survey_as_director_utf8(self):
        """
        Tests that director of contractor can download survey.
        """
        self.switch_to_user(A_DIRECTOR_USER_INFO)
        BizNavPage(self.browser).visit().change_role(A_COMPANY, self.contract['Contract Name'], self.course._course_key)\
            .click_survey().check_encoding_utf8(True).click_download_button()
        self._verify_csv_answers(self.expect_datas_as_director, True, 'utf8')

    def test_survey_as_staff(self):
        """
        Tests that staff of platfomer can download survey.
        """
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        survey_page_section.check_encoding_utf8(False).click_download_button()
        self._verify_csv_answers(self.expect_datas_as_staff, False, 'utf16')

    def test_survey_as_staff_utf8(self):
        """
        Tests that staff of platfomer can download survey.
        """
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, self.course._course_key).visit()
        survey_page_section = instructor_dashboard_page.select_survey()
        survey_page_section.check_encoding_utf8(True).click_download_button()
        self._verify_csv_answers(self.expect_datas_as_staff, False, 'utf8')

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

    def _verify_csv_answers(self, expect_data, enable_login_code_check, encoding):
        """
        Verify csv file.
        """
        # Get csv file. (Content_type is 'text/tab-separated-values')
        tmp_file = max(
                [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR) if f.count('.tsv')],
                key=os.path.getctime)
        csv_file = os.path.join(os.environ.get('SELENIUM_DRIVER_LOG_DIR', ''), self._testMethodName + '.csv')
        shutil.move(os.path.join(DOWNLOAD_DIR, tmp_file), csv_file)
        # Read csv
        with codecs.open(csv_file, encoding=encoding) as f:
            reader = csv.DictReader([row.encode('utf8') for row in f], delimiter="\t")
        if enable_login_code_check:
            csv_data = [[row.get('Login Code').decode('utf8'), row.get('Q1').decode('utf8'), row.get('Q2').decode('utf8'),
                         row.get('Q3').decode('utf8'), row.get('Q4').decode('utf8'), row.get('User Name').decode('utf8')
                         ] for row in reader]
        else:
            csv_data = [[row.get('Q1').decode('utf8'), row.get('Q2').decode('utf8'),
                         row.get('Q3').decode('utf8'), row.get('Q4').decode('utf8'), row.get('User Name').decode('utf8')
                         ] for row in reader]
        self.assertEqual(csv_data, expect_data)
