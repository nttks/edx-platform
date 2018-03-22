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
    Test instructor survey utf16 for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download')

    def validate_bom(self, content):
        return self.validate_bom_utf16(content)

    def get_survey_csv_rows_unicode(self, content):
        return self.get_survey_csv_rows_unicode_from_utf16(content)

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


class CourseOperationSurveyDownloadUTF8Test(CourseOperationSurveyDownloadTest, BizContractTestBase):
    """
    Test instructor survey utf8 for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download_utf8')

    def validate_bom(self, content):
        return self.validate_bom_utf8(content)

    def get_survey_csv_rows_unicode(self, content):
        return self.get_survey_csv_rows_unicode_from_utf8(content)


class LoginCodeEnabledCourseOperationSurveyDownloadTest(LoginCodeEnabledInstructorAPISurveyDownloadTestMixin, BizContractTestBase):
    """
    Test instructor survey utf16 for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download')

    def enable_login_code_check(self):
        return True

    def validate_bom(self, content):
        return self.validate_bom_utf16(content)

    def get_survey_csv_rows_unicode(self, content):
        return self.get_survey_csv_rows_unicode_from_utf16(content)

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


class LoginCodeEnabledCourseOperationSurveyDownloadUTF8Test(LoginCodeEnabledCourseOperationSurveyDownloadTest, BizContractTestBase):
    """
    Test instructor survey utf8 for biz endpoint.
    """

    def get_url(self):
        return reverse('biz:course_operation:survey_download_utf8')

    def enable_login_code_check(self):
        return True

    def validate_bom(self, content):
        return self.validate_bom_utf8(content)

    def get_survey_csv_rows_unicode(self, content):
        return self.get_survey_csv_rows_unicode_from_utf8(content)

