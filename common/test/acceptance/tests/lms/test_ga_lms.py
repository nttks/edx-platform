# -*- coding: utf-8 -*-
"""
End-to-end tests for the LMS.
"""

from datetime import datetime
from textwrap import dedent
from nose.plugins.attrib import attr

from bok_choy.promise import EmptyPromise
from ..ga_helpers import GA_COURSE_SCORER_USER_INFO, GA_GLOBAL_COURSE_CREATOR_USER_INFO, GA_OLD_COURSE_VIEWER_USER_INFO
from ..ga_role_helpers import GaccoTestRoleMixin
from ..helpers import (
    UniqueCourseTest,
    EventsTestMixin,
    load_data_str,
    generate_course_key,
    select_option_by_value,
    element_has_text
)
from ...fixtures.course import CourseFixture, XBlockFixtureDesc, CourseUpdateDesc
from ...pages.common.logout import LogoutPage
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.course_info import CourseInfoPage
from ...pages.lms.course_nav import CourseNavPage
from ...pages.lms.course_wiki import CourseWikiPage, CourseWikiEditPage
from ...pages.lms.dashboard import DashboardPage
from ...pages.lms.problem import ProblemPage
from ...pages.lms.progress import ProgressPage
from ...pages.lms.tab_nav import TabNavPage
from ...pages.lms.video.video import VideoPage
from ...pages.studio.settings import SettingsPage


@attr('shard_1')
class CourseWikiTestWithGaGlobalCourseCreator(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that verify the course wiki.
    """
    def _auto_auth(self):
        self.auto_auth_with_ga_global_course_creator(self.course_id)

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(CourseWikiTestWithGaGlobalCourseCreator, self).setUp()

        # self.course_info['number'] must be shorter since we are accessing the wiki. See TNL-1751
        self.course_info['number'] = self.unique_id[0:6]

        self.course_info_page = CourseInfoPage(self.browser, self.course_id)
        self.course_wiki_page = CourseWikiPage(self.browser, self.course_id)
        self.course_info_page = CourseInfoPage(self.browser, self.course_id)
        self.course_wiki_edit_page = CourseWikiEditPage(self.browser, self.course_id, self.course_info)
        self.tab_nav = TabNavPage(self.browser)

        CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        ).install()

        # Auto-auth register for the course
        self._auto_auth()

        # Access course wiki page
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Wiki')

    def _open_editor(self):
        self.course_wiki_page.open_editor()
        self.course_wiki_edit_page.wait_for_page()

    def test_edit_course_wiki(self):
        """
        Wiki page by default is editable for students.

        After accessing the course wiki,
        Replace the content of the default page
        Confirm new content has been saved

        """
        content = "hello"
        self._open_editor()
        self.course_wiki_edit_page.replace_wiki_content(content)
        self.course_wiki_edit_page.save_wiki_content()
        actual_content = unicode(self.course_wiki_page.q(css='.wiki-article p').text[0])
        self.assertEqual(content, actual_content)


@attr('shard_1')
class CourseWikiTestWithGaCourseScorer(CourseWikiTestWithGaGlobalCourseCreator):
    """
    Tests that verify the course wiki.
    """
    def _auto_auth(self):
        self.auto_auth_with_ga_course_scorer(self.course_id)


@attr('shard_1')
class HighLevelTabTestWithGaGlobalCourseCreator(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that verify each of the high-level tabs available within a course.
    """

    def _auto_auth(self):
        # Auto-auth register for the course
        self.auto_auth_with_ga_global_course_creator(self.course_id)

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(HighLevelTabTestWithGaGlobalCourseCreator, self).setUp()

        # self.course_info['number'] must be shorter since we are accessing the wiki. See TNL-1751
        self.course_info['number'] = self.unique_id[0:6]

        self.course_info_page = CourseInfoPage(self.browser, self.course_id)
        self.progress_page = ProgressPage(self.browser, self.course_id)
        self.course_nav = CourseNavPage(self.browser)
        self.tab_nav = TabNavPage(self.browser)
        self.video = VideoPage(self.browser)

        # Install a course with sections/problems, tabs, updates, and handouts
        course_fix = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        course_fix.add_update(CourseUpdateDesc(date='January 29, 2014', content='Test course update1'))
        course_fix.add_update(CourseUpdateDesc(date=datetime.now().strftime('%B %d, %Y'), content='Test course update2'))
        course_fix.add_update(CourseUpdateDesc(date='Welcome', content='Test course update3'))

        course_fix.add_handout('demoPDF.pdf')

        course_fix.add_children(
            XBlockFixtureDesc('static_tab', 'Test Static Tab'),
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    XBlockFixtureDesc('problem', 'Test Problem 1', data=load_data_str('multiple_choice.xml')),
                    XBlockFixtureDesc('problem', 'Test Problem 2', data=load_data_str('formula_problem.xml')),
                    XBlockFixtureDesc('html', 'Test HTML'),
                )
            ),
            XBlockFixtureDesc('chapter', 'Test Section 2').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection 2'),
                XBlockFixtureDesc('sequential', 'Test Subsection 3'),
            )
        ).install()

        self._auto_auth()

    def test_course_info(self):
        """
        Navigate to the course info page.
        """

        # Navigate to the course info page from the progress page
        self.progress_page.visit()
        self.tab_nav.go_to_tab('Course Info')

        # Expect just three updates
        self.assertEqual(self.course_info_page.num_updates, 3)

        # Expect just one new icon
        self.assertEqual(self.course_info_page.count_new_icon_updates, 1)

        # Expect a link to the demo handout pdf
        handout_links = self.course_info_page.handout_links
        self.assertEqual(len(handout_links), 1)
        self.assertIn('demoPDF.pdf', handout_links[0])

    def test_progress(self):
        """
        Navigate to the progress page.
        """
        # Navigate to the progress page from the info page
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Progress')

        # We haven't answered any problems yet, so assume scores are zero
        # Only problems should have scores; so there should be 2 scores.
        CHAPTER = 'Test Section'
        SECTION = 'Test Subsection'
        EXPECTED_SCORES = [(0, 3), (0, 1)]

        actual_scores = self.progress_page.scores(CHAPTER, SECTION)
        self.assertEqual(actual_scores, EXPECTED_SCORES)

    def test_static_tab(self):
        """
        Navigate to a static tab (course content)
        """
        # From the course info page, navigate to the static tab
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Test Static Tab')
        self.assertTrue(self.tab_nav.is_on_tab('Test Static Tab'))

    def test_wiki_tab_first_time(self):
        """
        Navigate to the course wiki tab. When the wiki is accessed for
        the first time, it is created on the fly.
        """

        course_wiki = CourseWikiPage(self.browser, self.course_id)
        # From the course info page, navigate to the wiki tab
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Wiki')
        self.assertTrue(self.tab_nav.is_on_tab('Wiki'))

        # Assert that a default wiki is created
        expected_article_name = "{org}.{course_number}.{course_run}".format(
            org=self.course_info['org'],
            course_number=self.course_info['number'],
            course_run=self.course_info['run']
        )
        self.assertEqual(expected_article_name, course_wiki.article_name)

    def test_courseware_nav(self):
        """
        Navigate to a particular unit in the courseware.
        """
        # Navigate to the courseware page from the info page
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Courseware')

        # Check that the courseware navigation appears correctly
        EXPECTED_SECTIONS = {
            'Test Section': ['Test Subsection'],
            'Test Section 2': ['Test Subsection 2', 'Test Subsection 3']
        }

        actual_sections = self.course_nav.sections
        for section, subsections in EXPECTED_SECTIONS.iteritems():
            self.assertIn(section, actual_sections)
            self.assertEqual(actual_sections[section], EXPECTED_SECTIONS[section])

        # Navigate to a particular section
        self.course_nav.go_to_section('Test Section', 'Test Subsection')

        # Check the sequence items
        EXPECTED_ITEMS = ['Test Problem 1', 'Test Problem 2', 'Test HTML']

        actual_items = self.course_nav.sequence_items
        self.assertEqual(len(actual_items), len(EXPECTED_ITEMS))
        for expected in EXPECTED_ITEMS:
            self.assertIn(expected, actual_items)


@attr('shard_1')
class HighLevelTabTestWithGaCourseScorer(HighLevelTabTestWithGaGlobalCourseCreator):
    """
    Tests that verify each of the high-level tabs available within a course.
    """

    def _auto_auth(self):
        # Auto-auth register for the course
        self.auto_auth_with_ga_course_scorer(self.course_id)


class PDFTextBooksTabTestWithGaGlobalCourseCreator(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that verify each of the textbook tabs available within a course.
    """
    def _auto_auth(self):
        self.auto_auth_with_ga_global_course_creator(self.course_id)

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(PDFTextBooksTabTestWithGaGlobalCourseCreator, self).setUp()

        self.course_info_page = CourseInfoPage(self.browser, self.course_id)
        self.tab_nav = TabNavPage(self.browser)

        # Install a course with TextBooks
        course_fix = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        # Add PDF textbooks to course fixture.
        for i in range(1, 3):
            course_fix.add_textbook("PDF Book {}".format(i), [{"title": "Chapter Of Book {}".format(i), "url": ""}])

        course_fix.install()

        # Auto-auth register for the course
        self._auto_auth()

    def test_verify_textbook_tabs(self):
        """
        Test multiple pdf textbooks loads correctly in lms.
        """
        self.course_info_page.visit()

        # Verify each PDF textbook tab by visiting, it will fail if correct tab is not loaded.
        for i in range(1, 3):
            self.tab_nav.go_to_tab("PDF Book {}".format(i))


class PDFTextBooksTabTestWithGaCourseScorer(PDFTextBooksTabTestWithGaGlobalCourseCreator):
    """
    Tests that verify each of the textbook tabs available within a course.
    """
    def _auto_auth(self):
        self.auto_auth_with_ga_course_scorer(self.course_id)


@attr('shard_1')
class VisibleToStaffOnlyTest(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that content with visible_to_staff_only set to True cannot be viewed by students.
    """
    def setUp(self):
        super(VisibleToStaffOnlyTest, self).setUp()

        course_fix = CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name']
        )

        course_fix.add_children(
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Subsection With Locked Unit').add_children(
                    XBlockFixtureDesc('vertical', 'Locked Unit', metadata={'visible_to_staff_only': True}).add_children(
                        XBlockFixtureDesc('html', 'Html Child in locked unit', data="<html>Visible only to staff</html>"),
                    ),
                    XBlockFixtureDesc('vertical', 'Unlocked Unit').add_children(
                        XBlockFixtureDesc('html', 'Html Child in unlocked unit', data="<html>Visible only to all</html>"),
                    )
                ),
                XBlockFixtureDesc('sequential', 'Unlocked Subsection').add_children(
                    XBlockFixtureDesc('vertical', 'Test Unit').add_children(
                        XBlockFixtureDesc('html', 'Html Child in visible unit', data="<html>Visible to all</html>"),
                    )
                ),
                XBlockFixtureDesc('sequential', 'Locked Subsection', metadata={'visible_to_staff_only': True}).add_children(
                    XBlockFixtureDesc('vertical', 'Test Unit').add_children(
                        XBlockFixtureDesc(
                            'html', 'Html Child in locked subsection', data="<html>Visible only to staff</html>"
                        )
                    )
                )
            )
        ).install()

        self.courseware_page = CoursewarePage(self.browser, self.course_id)
        self.course_nav = CourseNavPage(self.browser)

    def test_visible_to_ga_old_course_viewer(self):
        """
        Scenario: Content marked 'visible_to_staff_only' is not visible for students in the course
            Given some of the course content has been marked 'visible_to_staff_only'
            And I am logged on with an authorized ga_old_course_viewer account
            Then I can only see content without 'visible_to_staff_only' set to True
        """
        AutoAuthPage(
            self.browser,
            username=GA_OLD_COURSE_VIEWER_USER_INFO['username'],
            password=GA_OLD_COURSE_VIEWER_USER_INFO['password'],
            email=GA_OLD_COURSE_VIEWER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()

        self.courseware_page.visit()
        self.assertEqual(2, len(self.course_nav.sections['Test Section']))

        self.course_nav.go_to_section("Test Section", "Subsection With Locked Unit")
        self.assertEqual(["Html Child in unlocked unit"], self.course_nav.sequence_items)

        self.course_nav.go_to_section("Test Section", "Unlocked Subsection")
        self.assertEqual(["Html Child in visible unit"], self.course_nav.sequence_items)

    def test_visible_to_ga_global_course_creator(self):
        """
        Scenario: Content marked 'visible_to_staff_only' is not visible for students in the course
            Given some of the course content has been marked 'visible_to_staff_only'
            And I am logged on with an authorized ga_global_course_creator account
            Then I can only see content without 'visible_to_staff_only' set to True
        """
        """
        Scenario: All content is visible for a user marked is_staff (different from course staff)
            Given some of the course content has been marked 'visible_to_staff_only'
            And I am logged on with an authorized ga_global_course_creator account
            Then I can see all course content
        """
        AutoAuthPage(
            self.browser,
            username=GA_GLOBAL_COURSE_CREATOR_USER_INFO['username'],
            password=GA_GLOBAL_COURSE_CREATOR_USER_INFO['password'],
            email=GA_GLOBAL_COURSE_CREATOR_USER_INFO['email'],
            course_id=self.course_id
        ).visit()

        self.courseware_page.visit()
        self.assertEqual(3, len(self.course_nav.sections['Test Section']))

        self.course_nav.go_to_section("Test Section", "Subsection With Locked Unit")
        self.assertEqual(["Html Child in locked unit", "Html Child in unlocked unit"], self.course_nav.sequence_items)

        self.course_nav.go_to_section("Test Section", "Unlocked Subsection")
        self.assertEqual(["Html Child in visible unit"], self.course_nav.sequence_items)

        self.course_nav.go_to_section("Test Section", "Locked Subsection")
        self.assertEqual(["Html Child in locked subsection"], self.course_nav.sequence_items)

    def test_visible_to_ga_course_scorer(self):
        """
        Scenario: Content marked 'visible_to_staff_only' is not visible for students in the course
            Given some of the course content has been marked 'visible_to_staff_only'
            And I am logged on with an authorized ga_course_scorer account
            Then I can only see content without 'visible_to_staff_only' set to True
        """
        """
        Scenario: All content is visible for a user marked is_staff (different from course staff)
            Given some of the course content has been marked 'visible_to_staff_only'
            And I am logged on with an authorized ga_course_scorer account
            Then I can see all course content
        """
        self.add_course_role(self.course_id, 'Course Scorer', GA_COURSE_SCORER_USER_INFO['email'])

        # Logout and login as a ga_course_scorer
        AutoAuthPage(
            self.browser,
            username=GA_COURSE_SCORER_USER_INFO['username'],
            password=GA_COURSE_SCORER_USER_INFO['password'],
            email=GA_COURSE_SCORER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()

        self.courseware_page.visit()
        self.assertEqual(3, len(self.course_nav.sections['Test Section']))

        self.course_nav.go_to_section("Test Section", "Subsection With Locked Unit")
        self.assertEqual(["Html Child in locked unit", "Html Child in unlocked unit"], self.course_nav.sequence_items)

        self.course_nav.go_to_section("Test Section", "Unlocked Subsection")
        self.assertEqual(["Html Child in visible unit"], self.course_nav.sequence_items)

        self.course_nav.go_to_section("Test Section", "Locked Subsection")
        self.assertEqual(["Html Child in locked subsection"], self.course_nav.sequence_items)


@attr('shard_1')
class TooltipTestWithGaGlobalCourseCreator(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that tooltips are displayed
    """
    def _auto_auth(self):
        # Auto-auth register for the course
        self.auto_auth_with_ga_global_course_creator(self.course_id)

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(TooltipTestWithGaGlobalCourseCreator, self).setUp()

        self.course_info_page = CourseInfoPage(self.browser, self.course_id)
        self.tab_nav = TabNavPage(self.browser)

        course_fix = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        course_fix.add_children(
            XBlockFixtureDesc('static_tab', 'Test Static Tab'),
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    XBlockFixtureDesc('problem', 'Test Problem 1', data=load_data_str('multiple_choice.xml')),
                    XBlockFixtureDesc('problem', 'Test Problem 2', data=load_data_str('formula_problem.xml')),
                    XBlockFixtureDesc('html', 'Test HTML'),
                )
            )
        ).install()

        self.courseware_page = CoursewarePage(self.browser, self.course_id)
        # Auto-auth register for the course
        self._auto_auth()

    def test_tooltip(self):
        """
        Verify that tooltips are displayed when you hover over the sequence nav bar.
        """
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Courseware')

        self.assertTrue(self.courseware_page.tooltips_displayed())


@attr('shard_1')
class TooltipTestWithGaCourseScorer(TooltipTestWithGaGlobalCourseCreator):
    """
    Tests that tooltips are displayed
    """
    def _auto_auth(self):
        # Auto-auth register for the course
        self.auto_auth_with_ga_course_scorer(self.course_id)


@attr('shard_1')
class PreRequisiteCourseTest(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that pre-requisite course messages are displayed
    """

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(PreRequisiteCourseTest, self).setUp()

        CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        ).install()

        self.prc_info = {
            'org': 'test_org',
            'number': self.unique_id,
            'run': 'prc_test_run',
            'display_name': 'PR Test Course' + self.unique_id
        }

        CourseFixture(
            self.prc_info['org'], self.prc_info['number'],
            self.prc_info['run'], self.prc_info['display_name']
        ).install()

        pre_requisite_course_key = generate_course_key(
            self.prc_info['org'],
            self.prc_info['number'],
            self.prc_info['run']
        )
        self.pre_requisite_course_id = unicode(pre_requisite_course_key)

        self.dashboard_page = DashboardPage(self.browser)
        self.settings_page = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']

        )
        # Auto-auth register for the course
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

    def test_dashboard_message(self):
        """
         Scenario: Any course where there is a Pre-Requisite course Student dashboard should have
         appropriate messaging.
            Given that I am on the Student dashboard
            When I view a course with a pre-requisite course set
            Then At the bottom of course I should see course requirements message.'
        """

        # visit dashboard page and make sure there is not pre-requisite course message
        self.dashboard_page.visit()
        self.assertFalse(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and Login as a ga_old_course_viewer
        # self.switch_to_user(GA_OLD_COURSE_VIEWER_USER_INFO, self.course_id)
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_OLD_COURSE_VIEWER_USER_INFO['username'],
            password=GA_OLD_COURSE_VIEWER_USER_INFO['password'],
            email=GA_OLD_COURSE_VIEWER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit dashboard page and make sure there is not pre-requisite course message
        self.dashboard_page.visit()
        self.assertFalse(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and Login as a ga_global_course_creator
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_GLOBAL_COURSE_CREATOR_USER_INFO['username'],
            password=GA_GLOBAL_COURSE_CREATOR_USER_INFO['password'],
            email=GA_GLOBAL_COURSE_CREATOR_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit dashboard page and make sure there is pre-requisite course message
        self.dashboard_page.visit()
        self.assertFalse(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and Login as a ga_course_scorer
        LogoutPage(self.browser).visit()
        self.add_course_role(self.course_id, 'Course Scorer', GA_COURSE_SCORER_USER_INFO['email'])
        AutoAuthPage(
            self.browser,
            username=GA_COURSE_SCORER_USER_INFO['username'],
            password=GA_COURSE_SCORER_USER_INFO['password'],
            email=GA_COURSE_SCORER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit dashboard page and make sure there is pre-requisite course message
        self.dashboard_page.visit()
        self.assertFalse(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and login as a staff.
        LogoutPage(self.browser).visit()
        AutoAuthPage(self.browser, course_id=self.course_id, staff=True).visit()

        # visit course settings page and set pre-requisite course
        self.settings_page.visit()
        self._set_pre_requisite_course()

        # Logout and login as a student.
        LogoutPage(self.browser).visit()
        AutoAuthPage(self.browser, course_id=self.course_id, staff=False).visit()

        # visit dashboard page again now it should have pre-requisite course message
        self.dashboard_page.visit()
        EmptyPromise(lambda: self.dashboard_page.available_courses > 0, 'Dashboard page loaded').fulfill()
        self.assertTrue(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and Login as a ga_old_course_viewer
        # self.switch_to_user(GA_OLD_COURSE_VIEWER_USER_INFO)
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_OLD_COURSE_VIEWER_USER_INFO['username'],
            password=GA_OLD_COURSE_VIEWER_USER_INFO['password'],
            email=GA_OLD_COURSE_VIEWER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit dashboard page again now it should have pre-requisite course message
        self.dashboard_page.visit()
        EmptyPromise(lambda: self.dashboard_page.available_courses > 0, 'Dashboard page loaded').fulfill()
        self.assertTrue(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and Login as a ga_global_course_creator
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_GLOBAL_COURSE_CREATOR_USER_INFO['username'],
            password=GA_GLOBAL_COURSE_CREATOR_USER_INFO['password'],
            email=GA_GLOBAL_COURSE_CREATOR_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit dashboard page and make sure there is pre-requisite course message
        self.dashboard_page.visit()
        EmptyPromise(lambda: self.dashboard_page.available_courses > 0, 'Dashboard page loaded').fulfill()
        self.assertTrue(self.dashboard_page.pre_requisite_message_displayed())

        # Logout and Login as a ga_course_scorer
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_COURSE_SCORER_USER_INFO['username'],
            password=GA_COURSE_SCORER_USER_INFO['password'],
            email=GA_COURSE_SCORER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit dashboard page and make sure there is pre-requisite course message
        self.dashboard_page.visit()
        EmptyPromise(lambda: self.dashboard_page.available_courses > 0, 'Dashboard page loaded').fulfill()
        self.assertTrue(self.dashboard_page.pre_requisite_message_displayed())

    def _set_pre_requisite_course(self):
        """
        set pre-requisite course
        """
        select_option_by_value(self.settings_page.pre_requisite_course_options, self.pre_requisite_course_id)
        self.settings_page.save_changes()


@attr('shard_1')
class ProblemExecutionTestWithGaGlobalCourseCreator(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests of problems.
    """

    def _auto_auth(self):
        # Auto-auth register for the course
        self.auto_auth_with_ga_global_course_creator(self.course_id)

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(ProblemExecutionTestWithGaGlobalCourseCreator, self).setUp()

        self.course_info_page = CourseInfoPage(self.browser, self.course_id)
        self.course_nav = CourseNavPage(self.browser)
        self.tab_nav = TabNavPage(self.browser)

        # Install a course with sections and problems.
        course_fix = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        course_fix.add_asset(['python_lib.zip'])

        course_fix.add_children(
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    XBlockFixtureDesc('problem', 'Python Problem', data=dedent(
                        """\
                        <problem>
                        <script type="loncapa/python">
                        from number_helpers import seventeen, fortytwo
                        oneseven = seventeen()

                        def check_function(expect, ans):
                            if int(ans) == fortytwo(-22):
                                return True
                            else:
                                return False
                        </script>

                        <p>What is the sum of $oneseven and 3?</p>

                        <customresponse expect="20" cfn="check_function">
                            <textline/>
                        </customresponse>
                        </problem>
                        """
                    ))
                )
            )
        ).install()

        self._auto_auth()

    def test_python_execution_in_problem(self):
        # Navigate to the problem page
        self.course_info_page.visit()
        self.tab_nav.go_to_tab('Courseware')
        self.course_nav.go_to_section('Test Section', 'Test Subsection')

        problem_page = ProblemPage(self.browser)
        # text-transform property is uppercase in original, but none in gacco.css
        self.assertEqual(problem_page.problem_name, 'Python Problem')

        # Does the page have computation results?
        self.assertIn("What is the sum of 17 and 3?", problem_page.problem_text)

        # Fill in the answer correctly.
        problem_page.fill_answer("20")
        problem_page.click_check()
        self.assertTrue(problem_page.is_correct())

        # Fill in the answer incorrectly.
        problem_page.fill_answer("4")
        problem_page.click_check()
        self.assertFalse(problem_page.is_correct())


@attr('shard_1')
class ProblemExecutionTestWithGaCourseScorer(ProblemExecutionTestWithGaGlobalCourseCreator):
    """
    Tests of problems.
    """

    def _auto_auth(self):
        # Auto-auth register for the course
        self.auto_auth_with_ga_course_scorer(self.course_id)


@attr('shard_1')
class EntranceExamTest(UniqueCourseTest, GaccoTestRoleMixin):
    """
    Tests that course has an entrance exam.
    """

    def setUp(self):
        """
        Initialize pages and install a course fixture.
        """
        super(EntranceExamTest, self).setUp()

        CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        ).install()

        self.courseware_page = CoursewarePage(self.browser, self.course_id)
        self.settings_page = SettingsPage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

        # Auto-auth register for the course
        AutoAuthPage(self.browser, course_id=self.course_id).visit()

    def test_entrance_exam_section(self):
        """
         Scenario: Any course that is enabled for an entrance exam, should have entrance exam chapter at courseware
         page.
            Given that I am on the courseware page
            When I view the courseware that has an entrance exam
            Then there should be an "Entrance Exam" chapter.'
        """
        entrance_exam_link_selector = '.accordion .course-navigation .chapter .group-heading'
        # visit courseware page and make sure there is not entrance exam chapter.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertFalse(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a ga_old_course_viewer
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_OLD_COURSE_VIEWER_USER_INFO['username'],
            password=GA_OLD_COURSE_VIEWER_USER_INFO['password'],
            email=GA_OLD_COURSE_VIEWER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # self.switch_to_user(GA_OLD_COURSE_VIEWER_USER_INFO, self.course_id)
        # visit courseware page and make sure there is not entrance exam chapter.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertFalse(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a ga_global_course_creator
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_GLOBAL_COURSE_CREATOR_USER_INFO['username'],
            password=GA_GLOBAL_COURSE_CREATOR_USER_INFO['password'],
            email=GA_GLOBAL_COURSE_CREATOR_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit courseware page and make sure there is entrance exam chapter.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertFalse(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a ga_course_scorer
        LogoutPage(self.browser).visit()
        self.add_course_role(self.course_id, 'Course Scorer', GA_COURSE_SCORER_USER_INFO['email'])
        AutoAuthPage(
            self.browser,
            username=GA_COURSE_SCORER_USER_INFO['username'],
            password=GA_COURSE_SCORER_USER_INFO['password'],
            email=GA_COURSE_SCORER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit courseware page and make sure there is entrance exam chapter.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertFalse(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a staff.
        LogoutPage(self.browser).visit()
        AutoAuthPage(self.browser, course_id=self.course_id, staff=True).visit()

        # visit course settings page and set/enabled entrance exam for that course.
        self.settings_page.visit()
        self.settings_page.wait_for_page()
        self.assertTrue(self.settings_page.is_browser_on_page())
        self.settings_page.entrance_exam_field.click()
        self.settings_page.save_changes()

        # Logout and login as a student.
        LogoutPage(self.browser).visit()
        AutoAuthPage(self.browser, course_id=self.course_id, staff=False).visit()

        # visit course info page and make sure there is an "Entrance Exam" section.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertTrue(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a ga_old_course_viewer
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_OLD_COURSE_VIEWER_USER_INFO['username'],
            password=GA_OLD_COURSE_VIEWER_USER_INFO['password'],
            email=GA_OLD_COURSE_VIEWER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # self.switch_to_user(GA_OLD_COURSE_VIEWER_USER_INFO, self.course_id)
        # visit courseware page and make sure there is not entrance exam chapter.

        # visit course info page and make sure there is an "Entrance Exam" section.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertTrue(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a ga_global_course_creator
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_GLOBAL_COURSE_CREATOR_USER_INFO['username'],
            password=GA_GLOBAL_COURSE_CREATOR_USER_INFO['password'],
            email=GA_GLOBAL_COURSE_CREATOR_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit courseware page and make sure there is entrance exam chapter.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertTrue(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))

        # Logout and login as a ga_course_scorer
        LogoutPage(self.browser).visit()
        AutoAuthPage(
            self.browser,
            username=GA_COURSE_SCORER_USER_INFO['username'],
            password=GA_COURSE_SCORER_USER_INFO['password'],
            email=GA_COURSE_SCORER_USER_INFO['email'],
            course_id=self.course_id
        ).visit()
        # visit courseware page and make sure there is entrance exam chapter.
        self.courseware_page.visit()
        self.courseware_page.wait_for_page()
        self.assertTrue(element_has_text(
            page=self.courseware_page,
            css_selector=entrance_exam_link_selector,
            text='Entrance Exam'
        ))
