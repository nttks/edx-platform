# -*- coding: utf-8 -*-
"""
End-to-end tests for survey feature
"""

import unittest

import bok_choy.browser
from ...fixtures.course import CourseFixture, XBlockFixtureDesc
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.ga_course_nav import CourseNavPage
from ...pages.lms.ga_survey import SurveyPage
from ..ga_helpers import GaccoTestMixin
from ..helpers import UniqueCourseTest, load_data_str


@unittest.skip("Skip until survey unit is fixed")
class SurveyTest(UniqueCourseTest, GaccoTestMixin):
    """
    Tests that the survey functionality works
    """

    def setUp(self):
        """
        Initiailizes the page object and create a test user
        """
        super(SurveyTest, self).setUp()

        course_fix = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        course_fix.add_children(
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    XBlockFixtureDesc('vertical', 'Test Unit').add_children(
                        XBlockFixtureDesc('html', 'Test HTML', data=load_data_str('ga_survey.html'))
                    )
                )
            )
        ).install()

        # Auto-auth register for the course
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

        # Set window size
        self.setup_window_size_for_pc()

    def _visit_survey_page(self):
        """
        Visits survey page
        """
        CoursewarePage(self.browser, self.course_id).visit()
        self.course_nav = CourseNavPage(self.browser)
        self.course_nav.go_to_section('Test Section', 'Test Subsection')
        self.survey_page = SurveyPage(self.browser).wait_for_page()

    def test_survey_success(self):
        """
        Tests that submitting with valid values is successful
        """
        # Visit survey page
        self._visit_survey_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_success__1')
        self.assertTrue(self.survey_page.is_submit_button_enabled())

        # Submit
        self.survey_page.fill_item('Q1', '1')
        self.survey_page.fill_item('Q2', '2')
        self.survey_page.fill_item('Q3', 'yes')
        self.survey_page.fill_item('Q4', u'あああ')
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_success__2')
        self.survey_page.submit()

        # Verify message
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_success__3')
        self.assertIn(u"ご回答ありがとうございました。", self.survey_page.wait_for_messages())
        self.assertFalse(self.survey_page.is_submit_button_enabled())

        # Visit again
        self._visit_survey_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_success__4')
        self.assertIn(u"このアンケートは既に回答済みです。", self.survey_page.wait_for_messages())
        self.assertFalse(self.survey_page.is_submit_button_enabled())

    def test_survey_with_empty_item(self):
        """
        Tests that submitting with empty item is not successful
        """
        # Visit survey page
        self._visit_survey_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_with_empty_item__1')
        self.assertTrue(self.survey_page.is_submit_button_enabled())

        # Submit
        self.survey_page.fill_item('Q1', '1')
        self.survey_page.fill_item('Q2', '2')
        self.survey_page.fill_item('Q3', 'yes')
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_with_empty_item__2')
        self.survey_page.submit()

        # Verify message
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_with_empty_item__3')
        self.assertIn(u"問4 は必須入力です。", self.survey_page.wait_for_messages())
        self.assertTrue(self.survey_page.is_submit_button_enabled())

    def test_survey_with_over_maxlength_item(self):
        """
        Tests that submitting with over maxlength item is not successful
        """
        # Visit survey page
        self._visit_survey_page()
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_with_over_maxlength_item__1')
        self.assertTrue(self.survey_page.is_submit_button_enabled())

        # Submit
        self.survey_page.fill_item('Q1', '1')
        self.survey_page.fill_item('Q2', '2')
        self.survey_page.fill_item('Q3', 'yes')
        self.survey_page.fill_item('Q4', u'あ' * 1001)
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_with_over_maxlength_item__2')
        self.survey_page.submit()

        # Verify message
        bok_choy.browser.save_screenshot(self.browser, 'test_survey_with_over_maxlength_item__3')
        self.assertIn(u"問4 は1000字以下で入力してください。", self.survey_page.wait_for_messages())
        self.assertTrue(self.survey_page.is_submit_button_enabled())
