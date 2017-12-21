# -*- coding: utf-8 -*-
"""
Tests the "preview" selector in the LMS that allows changing between Staff, Student, and Content Groups.
"""
from nose.plugins.attrib import attr

from ..ga_role_helpers import GaccoTestRoleMixin
from ..helpers import UniqueCourseTest, create_user_partition_json
from ...pages.studio.auto_auth import AutoAuthPage
from ...pages.lms.courseware import CoursewarePage
from ...pages.lms.staff_view import StaffPage
from ...fixtures.course import CourseFixture, XBlockFixtureDesc
from xmodule.partitions.partitions import Group
from textwrap import dedent


@attr('shard_3')
class StaffViewTest(UniqueCourseTest):
    """
    Tests that verify the staff view.
    """
    USERNAME = "STAFF_TESTER"
    EMAIL = "johndoe@example.com"

    def _auto_auth(self):
        AutoAuthPage(self.browser, username=self.USERNAME, email=self.EMAIL,
                     course_id=self.course_id, staff=True).visit()

    def setUp(self):
        super(StaffViewTest, self).setUp()

        self.courseware_page = CoursewarePage(self.browser, self.course_id)

        # Install a course with sections/problems, tabs, updates, and handouts
        self.course_fixture = CourseFixture(
            self.course_info['org'], self.course_info['number'],
            self.course_info['run'], self.course_info['display_name']
        )

        self.populate_course_fixture(self.course_fixture)  # pylint: disable=no-member

        self.course_fixture.install()

        # Auto-auth register for the course.
        # Do this as global staff so that you will see the Staff View
        self._auto_auth()

    def _goto_staff_page(self):
        """
        Open staff page with assertion
        """
        self.courseware_page.visit()
        staff_page = StaffPage(self.browser, self.course_id)
        self.assertEqual(staff_page.staff_view_mode, 'Staff')
        return staff_page


@attr('shard_3')
class CourseWithoutContentGroupsTest(StaffViewTest):
    """
    Setup for tests that have no content restricted to specific content groups.
    """

    def populate_course_fixture(self, course_fixture):
        """
        Populates test course with chapter, sequential, and 2 problems.
        """
        problem_data = dedent("""
            <problem markdown="Simple Problem" max_attempts="" weight="">
              <p>Choose Yes.</p>
              <choiceresponse>
                <checkboxgroup>
                  <choice correct="true">Yes</choice>
                </checkboxgroup>
              </choiceresponse>
            </problem>
        """)

        course_fixture.add_children(
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    XBlockFixtureDesc('problem', 'Test Problem 1', data=problem_data),
                    XBlockFixtureDesc('problem', 'Test Problem 2', data=problem_data)
                )
            )
        )


@attr('shard_3')
class StaffViewToggleTest(CourseWithoutContentGroupsTest, GaccoTestRoleMixin):
    """
    Tests for the staff view toggle button.
    """
    def test_instructor_tab_visibility_with_ga_global_course_creator(self):
        """
        Test that the instructor tab is always hidden by GaGlobalCourseCreator.
        """
        self.logout()
        self.auto_auth_with_ga_global_course_creator(self.course_id)
        self.courseware_page.visit()
        self.assertFalse(self.courseware_page.has_tab('Instructor'))

    def test_instructor_tab_visibility_with_ga_course_scorer(self):
        """
        Test that the instructor tab is hidden when viewing as a student.
        """
        self.logout()
        self.auto_auth_with_ga_course_scorer(self.course_id)
        course_page = self._goto_staff_page()
        self.assertTrue(course_page.has_tab('Instructor'))
        course_page.set_staff_view_mode('Student')
        self.assertEqual(course_page.staff_view_mode, 'Student')
        self.assertFalse(course_page.has_tab('Instructor'))


@attr('shard_3')
class StaffDebugTestWithGaCourseScorer(CourseWithoutContentGroupsTest, GaccoTestRoleMixin):
    """
    Tests that verify the staff debug info.
    """
    def _auto_auth(self):
        self.user_info = self.auto_auth_with_ga_course_scorer(self.course_id)

    def test_enabled_staff_debug(self):
        """
        Test that ga_course_scorer can view staff debug info
        """
        staff_page = self._goto_staff_page()

        # 'Staff Debug Info' is capitalized.
        # 'text-transform: uppercase' is set for .instructor-info-action
        # in lms/static/sass/course/courseware/_courseware.scss
        self.assertTrue(u'STAFF DEBUG INFO' in staff_page.q(css='a.instructor-info-action').text)

    def test_reset_attempts_empty(self):
        """
        Test that we reset even when there is no student state
        """

        staff_debug_page = self._goto_staff_page().open_staff_debug_info()
        staff_debug_page.reset_attempts()
        msg = staff_debug_page.idash_msg[0]
        self.assertEqual(u'Successfully reset the attempts '
                         'for user {}'.format(self.user_info['username']), msg)

    def test_reset_attempts_state(self):
        """
        Successfully reset the student attempts
        """
        staff_page = self._goto_staff_page()
        staff_page.answer_problem()

        staff_debug_page = staff_page.open_staff_debug_info()
        staff_debug_page.reset_attempts()
        msg = staff_debug_page.idash_msg[0]
        self.assertEqual(u'Successfully reset the attempts '
                         'for user {}'.format(self.user_info['username']), msg)

    def test_student_by_email(self):
        """
        Successfully reset the student attempts using their email address
        """
        staff_page = self._goto_staff_page()
        staff_page.answer_problem()

        staff_debug_page = staff_page.open_staff_debug_info()
        staff_debug_page.reset_attempts(self.user_info['email'])
        msg = staff_debug_page.idash_msg[0]
        self.assertEqual(u'Successfully reset the attempts '
                         'for user {}'.format(self.user_info['email']), msg)

    def test_reset_attempts_for_problem_loaded_via_ajax(self):
        """
        Successfully reset the student attempts for problem loaded via ajax.
        """
        staff_page = self._goto_staff_page()
        staff_page.load_problem_via_ajax()
        staff_page.answer_problem()

        staff_debug_page = staff_page.open_staff_debug_info()
        staff_debug_page.reset_attempts()
        msg = staff_debug_page.idash_msg[0]
        self.assertEqual(u'Successfully reset the attempts '
                         'for user {}'.format(self.user_info['username']), msg)


@attr('shard_3')
class StaffDebugTestWithGaGlobalCourseCreator(CourseWithoutContentGroupsTest, GaccoTestRoleMixin):
    """
    Tests that verify the staff debug info.
    """
    def _auto_auth(self):
        self.user_info = self.auto_auth_with_ga_global_course_creator(self.course_id)

    def test_disabled_staff_debug(self):
        """
        Test that ga_global_course_creator cannot view staff debug info
        """
        courseware_page = self.courseware_page.visit()

        self.assertFalse(courseware_page.q(css='a.instructor-info-action').is_present())


@attr('shard_3')
class StudentHistoryViewTestWithGaCourseScorer(CourseWithoutContentGroupsTest, GaccoTestRoleMixin):
    """
    Tests that verify the Student History View.
    """
    def _auto_auth(self):
        self.user_info = self.auto_auth_with_ga_course_scorer(self.course_id)

    def test_enabled_student_history_view(self):
        """
        Test that ga_course_scorer can view Student history
        """
        staff_page = self._goto_staff_page()

        # 'Submission history' is capitalized.
        # 'text-transform: uppercase' is set for .instructor-info-action
        # in lms/static/sass/course/courseware/_courseware.scss
        self.assertTrue(u'SUBMISSION HISTORY' in staff_page.q(css='a.instructor-info-action').text)


@attr('shard_3')
class StudentHistoryViewTestWithGaGlobalCourseCreator(CourseWithoutContentGroupsTest, GaccoTestRoleMixin):
    """
    Tests that verify the Student History View.
    """
    def _auto_auth(self):
        self.user_info = self.auto_auth_with_ga_global_course_creator(self.course_id)

    def test_disabled_student_history_view(self):
        """
        Test that ga_global_course_creator can view Student history
        """
        courseware_page = self.courseware_page.visit()
        self.assertFalse(courseware_page.q(css='a.instructor-info-action').is_present())


@attr('shard_3')
class CourseWithContentGroupsTest(StaffViewTest, GaccoTestRoleMixin):
    """
    Verifies that changing the "View this course as" selector works properly for content groups.
    """

    def _auto_auth(self):
        self.auto_auth_with_ga_global_course_creator(self.course_id)

    def setUp(self):
        super(CourseWithContentGroupsTest, self).setUp()
        # pylint: disable=protected-access
        self.course_fixture._update_xblock(self.course_fixture._course_location, {
            "metadata": {
                u"user_partitions": [
                    create_user_partition_json(
                        0,
                        'Configuration alpha,beta',
                        'Content Group Partition',
                        [Group("0", 'alpha'), Group("1", 'beta')],
                        scheme="cohort"
                    )
                ],
            },
        })

    def populate_course_fixture(self, course_fixture):
        """
        Populates test course with chapter, sequential, and 3 problems.
        One problem is visible to all, one problem is visible only to Group "alpha", and
        one problem is visible only to Group "beta".
        """
        problem_data = dedent("""
            <problem markdown="Simple Problem" max_attempts="" weight="">
              <p>Choose Yes.</p>
              <choiceresponse>
                <checkboxgroup>
                  <choice correct="true">Yes</choice>
                </checkboxgroup>
              </choiceresponse>
            </problem>
        """)

        self.alpha_text = "VISIBLE TO ALPHA"
        self.beta_text = "VISIBLE TO BETA"
        self.everyone_text = "VISIBLE TO EVERYONE"

        course_fixture.add_children(
            XBlockFixtureDesc('chapter', 'Test Section').add_children(
                XBlockFixtureDesc('sequential', 'Test Subsection').add_children(
                    XBlockFixtureDesc('vertical', 'Test Unit').add_children(
                        XBlockFixtureDesc(
                            'problem', self.alpha_text, data=problem_data, metadata={"group_access": {0: [0]}}
                        ),
                        XBlockFixtureDesc(
                            'problem', self.beta_text, data=problem_data, metadata={"group_access": {0: [1]}}
                        ),
                        XBlockFixtureDesc('problem', self.everyone_text, data=problem_data)
                    )
                )
            )
        )

    def test_staff_sees_all_problems_with_ga_global_course_creator(self):
        """
        Scenario: GaGlobalCourseCreator see all problems
        Given I have a course with a cohort user partition
        And problems that are associated with specific groups in the user partition
        When I view the courseware in the LMS with staff access
        Then I see all the problems, regardless of their group_access property
        """
        self.logout()
        self.auto_auth_with_ga_global_course_creator(self.course_id)
        self.courseware_page.visit()
        verify_expected_problem_visibility(self, self.courseware_page, [self.alpha_text, self.beta_text, self.everyone_text])

    def test_staff_sees_all_problems_with_ga_course_scorer(self):
        """
        Scenario: GaCourseScorer see all problems
        Given I have a course with a cohort user partition
        And problems that are associated with specific groups in the user partition
        When I view the courseware in the LMS with staff access
        Then I see all the problems, regardless of their group_access property
        """
        self.logout()
        self.auto_auth_with_ga_course_scorer(self.course_id)
        self.courseware_page.visit()
        verify_expected_problem_visibility(self, self.courseware_page, [self.alpha_text, self.beta_text, self.everyone_text])


def verify_expected_problem_visibility(test, courseware_page, expected_problems):
    """
    Helper method that checks that the expected problems are visible on the current page.
    """
    test.assertEqual(
        len(expected_problems), courseware_page.num_xblock_components, "Incorrect number of visible problems"
    )
    for index, expected_problem in enumerate(expected_problems):
        test.assertIn(expected_problem, courseware_page.xblock_components[index].text)
