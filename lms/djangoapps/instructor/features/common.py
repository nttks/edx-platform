"""
Define common steps for instructor dashboard acceptance tests.
"""

# pylint: disable=missing-docstring
# pylint: disable=redefined-outer-name

from __future__ import absolute_import

from lettuce import world, step
from mock import patch
from nose.tools import assert_in, assert_true, assert_false  # pylint: disable=no-name-in-module

from courseware.tests.factories import (
    StaffFactory, InstructorFactory, BetaTesterFactory, GlobalStaffFactory, GaExtractDataAuthorityFactory,
)


@step(u'Given I am "([^"]*)" for a very large course')
def make_staff_or_instructor_for_large_course(step, role):
    make_large_course(step, role)


@patch.dict('courseware.access.settings.FEATURES', {"MAX_ENROLLMENT_INSTR_BUTTONS": 0})
def make_large_course(step, role):
    i_am_staff_or_instructor(step, role)


@step(u'Given I am "([^"]*)" for a course')
def i_am_staff_or_instructor(step, role):  # pylint: disable=unused-argument
    ## In summary: makes a test course, makes a new Staff or Instructor or BetaTester or GlobalStaff user
    ## (depending on `role`), and logs that user in to the course

    # Store the role
    assert_in(role, ['admin', 'instructor', 'staff', 'beta_tester'])

    # Clear existing courses to avoid conflicts
    world.clear_courses()

    # Create a new course
    course = world.CourseFactory.create(
        org='edx',
        number='999',
        display_name='Test Course'
    )

    world.course_key = course.id
    # Log in as an admin or an instructor or staff for the course
    if role == 'admin':
        world.role = 'admin'
        # Make & register a global staff
        world.admin = GlobalStaffFactory()
        world.enroll_user(world.admin, world.course_key)

        world.log_in(
            username=world.admin.username,
            password='test',
            email=world.admin.email,
            name=world.admin.profile.name
        )

    elif role == 'instructor':
        world.role = 'instructor'
        # Make & register an instructor for the course
        world.instructor = InstructorFactory(course_key=world.course_key)
        world.enroll_user(world.instructor, world.course_key)

        world.log_in(
            username=world.instructor.username,
            password='test',
            email=world.instructor.email,
            name=world.instructor.profile.name
        )

    elif role == 'staff':
        world.role = 'staff'
        # Make & register a staff member
        world.staff = StaffFactory(course_key=world.course_key)
        world.enroll_user(world.staff, world.course_key)

        world.log_in(
            username=world.staff.username,
            password='test',
            email=world.staff.email,
            name=world.staff.profile.name
        )

    else:
        world.role = 'beta_tester'
        # Make & register a beta tester for the course
        world.beta_tester = BetaTesterFactory(course_key=world.course_key)
        world.enroll_user(world.beta_tester, world.course_key)

        world.log_in(
            username=world.beta_tester.username,
            password='test',
            email=world.beta_tester.email,
            name=world.beta_tester.profile.name
        )


@step(u'I am given extra "([^"]*)" for a course')
def i_am_given_extra_role(step, extra_role):  # pylint: disable=unused-argument
    # Should prepare a user with particular role in advance.
    assert_in(world.role, ['admin', 'instructor', 'staff', 'beta_tester'])

    if world.role == 'admin':
        user = world.admin
    elif world.role == 'instructor':
        user = world.instructor
    elif world.role == 'staff':
        user = world.staff
    elif world.role == 'beta_tester':
        user = world.beta_tester

    if extra_role == 'ga_extract_data_authority':
        GaExtractDataAuthorityFactory.add_users(world.course_key, user)


def go_to_section(section_name):
    # section name should be one of
    # course_info, membership, student_admin, data_download, analytics, send_email
    world.visit(u'/courses/{}'.format(world.course_key))
    world.css_click(u'a[href="/courses/{}/instructor"]'.format(world.course_key))
    world.css_click('a[data-section="{0}"]'.format(section_name))


@step(u"I visit the instructor dashboard")
def go_to_instructor_dashboard(step):  # pylint: disable=unused-argument
    world.visit(u'/courses/{}'.format(world.course_key))
    world.css_click(u'a[href="/courses/{}/instructor"]'.format(world.course_key))


@step(u'I see a "([^"]*)" tab')
def find_tab(step, tab_name):  # pylint: disable=unused-argument
    assert_true(verify_tab_is_visible(tab_name))


@step(u'I do not see a "([^"]*)" tab')
def find_no_such_tab(step, tab_name):  # pylint: disable=unused-argument
    assert_false(verify_tab_is_visible(tab_name))


def verify_tab_is_visible(tab_name):
    tabs = world.css_find('ul.instructor-nav > li.nav-item')
    return any([tab.text.upper() == tab_name.upper() for tab in tabs])


@step(u'I click "([^"]*)"')
def click_a_button(step, button):  # pylint: disable=unused-argument

    if button == "Generate Grade Report":
        # Go to the data download section of the instructor dash
        go_to_section("data_download")

        # Click generate grade report button
        world.css_click('input[name="calculate-grades-csv"]')

        # Expect to see a message that grade report is being generated
        expected_msg = "The grade report is being created." \
                       " To view the status of the report, see" \
                       " Pending Instructor Tasks below."
        world.wait_for_visible('#report-request-response')
        assert_in(
            expected_msg, world.css_text('#report-request-response'),
            msg="Could not find grade report generation success message."
        )

    elif button == "Grading Configuration":
        # Go to the data download section of the instructor dash
        go_to_section("data_download")

        world.css_click('input[name="dump-gradeconf"]')

    elif button == "List enrolled students' profile information":
        # Go to the data download section of the instructor dash
        go_to_section("data_download")

        world.css_click('input[name="list-profiles"]')

    elif button == "Download profile information as a CSV":
        # Go to the data download section of the instructor dash
        go_to_section("data_download")

        world.css_click('input[name="list-profiles-csv"]')

    else:
        raise ValueError("Unrecognized button option " + button)


@step(u'I see "([^"]*)" button')
def i_see_a_button(step, button_text):  # pylint: disable=unused-argument
    assert_true(world.is_button_visible_by_text(button_text))


@step(u'I do not see "([^"]*)" button')
def i_do_not_see_a_button(step, button_text):  # pylint: disable=unused-argument
    assert_false(world.is_button_visible_by_text(button_text))


@step(u'I visit the "([^"]*)" tab')
def click_a_button(step, tab_name):  # pylint: disable=unused-argument
    # course_info, membership, student_admin, data_download, analytics, send_email
    tab_name_dict = {
        'Course Info': 'course_info',
        'Membership': 'membership',
        'Cohorts': 'cohort_management',
        'Student Admin': 'student_admin',
        'Data Download': 'data_download',
        'Analytics': 'analytics',
        'Email': 'send_email',
        'Survey': 'survey',
        'Progress Report': 'progress_report',
    }
    go_to_section(tab_name_dict[tab_name])
