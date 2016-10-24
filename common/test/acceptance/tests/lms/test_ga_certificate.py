"""
End-to-end tests for certificate on dashboard
"""
import datetime

from bok_choy.web_app_test import WebAppTest

from ...fixtures.course import CourseFixture
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_dashboard import DashboardPage
from ..ga_helpers import GaccoTestMixin


class CertificateDashboardTest(WebAppTest, GaccoTestMixin):
    """
    Tests that the certificate on dashboard
    """

    def _create_course(self, org, number, run, display_name):
        yesterday = datetime.datetime.now() + datetime.timedelta(days=-1)
        return CourseFixture(org, number, run, display_name, end_date=yesterday).install()

    def setUp(self):
        super(CertificateDashboardTest, self).setUp()

        number = "335535897951379478207964576572017930000"
        self.honor_course_name = 'Honor Course title ' + number
        self.audit_course_name = 'Audit Course title ' + number

        # user enrolled (honor)
        self._create_course('ga_test_org', number, 'test_run_001', self.honor_course_name)
        # user enrolled (audit)
        self._create_course('ga_test_org', number, 'test_run_002', self.audit_course_name)

        username = 'ga_testcert'
        password = 'ga_testuser'
        email = 'ga_cert@example.com'

        AutoAuthPage(self.browser, username=username, password=password, email=email).visit()

        self.dashboard_page = DashboardPage(self.browser)

    def test_certificate_message(self):
        # visit dashboard
        self.dashboard_page.visit()

        # same message enrollment honor and audit
        self.assertEqual(
            self.dashboard_page.get_status_message(self.honor_course_name),
            self.dashboard_page.get_status_message(self.audit_course_name)
        )
