from django.core.urlresolvers import reverse

from instructor.tests.test_api import InstructorAPISurveyDownloadTestMixin, LoginCodeEnabledInstructorAPISurveyDownloadTestMixin

from biz.djangoapps.ga_invitation.tests.test_views import BizContractTestBase


class CourseOperationViewsTest(BizContractTestBase):

    def test_survey(self):
        self.setup_user()
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course_spoc1):
            self.assert_request_status_code(200, reverse('biz:course_operation:survey'))


class CourseOperationSurveyDownloadTest(InstructorAPISurveyDownloadTestMixin, BizContractTestBase):
    """
    Test instructor survey for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download')

    def test_get_survey_not_allowed_method(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self.get_url())
        self.assertEqual(405, response.status_code)

    def test_get_survey(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(CourseOperationSurveyDownloadTest, self).test_get_survey()

    def test_get_survey_when_data_is_empty(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(CourseOperationSurveyDownloadTest, self).test_get_survey_when_data_is_empty()

    def test_get_survey_when_data_is_broken(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(CourseOperationSurveyDownloadTest, self).test_get_survey_when_data_is_broken()


class LoginCodeEnabledCourseOperationSurveyDownloadTest(LoginCodeEnabledInstructorAPISurveyDownloadTestMixin, BizContractTestBase):
    """
    Test instructor survey for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download')

    def enable_login_code_check(self):
        return True

    def test_get_survey_not_allowed_method(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            response = self.client.get(self.get_url())
        self.assertEqual(405, response.status_code)

    def test_get_survey(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(LoginCodeEnabledCourseOperationSurveyDownloadTest, self).test_get_survey()

    def test_get_survey_when_data_is_empty(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(LoginCodeEnabledCourseOperationSurveyDownloadTest, self).test_get_survey_when_data_is_empty()

    def test_get_survey_when_data_is_broken(self):
        with self.skip_check_course_selection(current_contract=self.contract, current_course=self.course):
            super(LoginCodeEnabledCourseOperationSurveyDownloadTest, self).test_get_survey_when_data_is_broken()