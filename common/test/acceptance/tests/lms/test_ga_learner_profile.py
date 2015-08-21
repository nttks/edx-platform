"""
End-to-end tests for Student's Profile Page.
"""
from bok_choy.web_app_test import WebAppTest
from uuid import uuid4

from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.ga_dashboard import DashboardPage
from ...pages.lms.ga_discussion import DiscussionUserProfilePage
from ..ga_helpers import GaccoTestMixin
from ..helpers import UniqueCourseTest

from ...fixtures.course import CourseFixture
from ...fixtures.discussion import (
    UserProfileViewFixture,
    Thread,
)


class LearnerProfilePageTest(WebAppTest, GaccoTestMixin):
    """
    Tests that verify a student's profile page.
    """

    def setUp(self):
        super(LearnerProfilePageTest, self).setUp()
        # Set window size
        self.setup_window_size_for_pc()

    def _log_in_as_unique_user(self):
        """
        Create a unique user and return the account's username and id.
        """
        username = "test_{uuid}".format(uuid=self.unique_id[0:6])
        AutoAuthPage(self.browser, username=username).visit()

    def test_dashboard_learner_profile_link(self):
        """
        Scenario: Verify that my profile link is `NOT` present on dashboard page.

        Given that I am a registered user.
        When I go to Dashboard page.
        And I click on username dropdown.
        Then I don't see My Profile link in the dropdown menu.
        """

        self._log_in_as_unique_user()
        dashboard_page = DashboardPage(self.browser)
        dashboard_page.visit()
        dashboard_page.click_username_dropdown()
        self.assertTrue('My Profile' not in dashboard_page.username_dropdown_link_text)


class DiscussionUserProfileTest(UniqueCourseTest, GaccoTestMixin):
    """
    Tests for user profile page in discussion tab.
    """

    PROFILED_USERNAME = "profiled-user"

    def setUp(self):
        super(DiscussionUserProfileTest, self).setUp()
        CourseFixture(**self.course_info).install()
        # The following line creates a user enrolled in our course, whose
        # threads will be viewed, but not the one who will view the page.
        self.profiled_user_id = AutoAuthPage(
            self.browser,
            username=self.PROFILED_USERNAME,
            course_id=self.course_id
        ).visit().get_user_id()
        # now create a second user who will view the profile.
        self.user_id = AutoAuthPage(
            self.browser,
            course_id=self.course_id
        ).visit().get_user_id()
        # Set window size
        self.setup_window_size_for_pc()

    def _create_profile_page(self, num_threads):
        """
        Create discussion profile page.
        See ..discussion.test_discussion.DiscussionUserProfileTest.check_pages
        """
        # set up the stub server to return the desired amount of thread results
        threads = [Thread(id=uuid4().hex) for _ in range(num_threads)]
        UserProfileViewFixture(threads).push()
        # navigate to default view (page 1)
        page = DiscussionUserProfilePage(
            self.browser,
            self.course_id,
            self.profiled_user_id,
            self.PROFILED_USERNAME
        )
        page.visit()

        return page

    def test_discussion_learner_profile_link(self):
        """
        Scenario: Verify that learner-profile link is `NOT` present on forum discussions page.

        Given that I am on discussion forum user's profile page.
        And I can see a username on left sidebar but `NOT` link element
        """
        page = self._create_profile_page(1)
        self.assertFalse(page.exists_sidebar_username_link_element())
