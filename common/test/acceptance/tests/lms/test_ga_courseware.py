"""
End-to-end tests for the LMS.
"""
import ddt

from ..ga_helpers import GaccoTestMixin, SUPER_USER_INFO
from ..helpers import UniqueCourseTest
from ...fixtures.course import CourseFixture, XBlockFixtureDesc
from ...pages.lms.auto_auth import AutoAuthPage
from ...pages.lms.course_nav import CourseNavPage
from ...pages.lms.courseware import CoursewarePage, CoursewareSequentialTabPage
from ...pages.lms.ga_django_admin import DjangoAdminPage
from ...pages.lms.problem import ProblemPage
from ...pages.studio.ga_overview import CourseOutlinePage
from textwrap import dedent


@ddt.ddt
class CoursewareProgressRestrictionTest(UniqueCourseTest, GaccoTestMixin):

    def setUp(self):
        super(CoursewareProgressRestrictionTest, self).setUp()

        self.user_info = {
            'username': 'STUDENT_TESTER_2147',
            'password': 'STUDENT_PASS',
            'email': 'student2147@example.com'
        }
        self.user_info_staff = {
            'username': 'STAFF_TESTER_2147',
            'password': 'STAFF_PASS',
            'email': 'staff2147@example.com'
        }

        self.course_info = {
            'org': 'test_org_00003',
            'number': self._testMethodName,
            'run': 'test_run_00003',
            'display_name': 'Progress Restriction Course'
        }

        self.course_fixture = CourseFixture(
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run'],
            self.course_info['display_name']
        )

        problem1_xml = dedent("""
            <problem>
            <p>Answer is A</p>
            <stringresponse answer="A">
                <textline size="20"/>
            </stringresponse>
            </problem>
        """)
        problem2_xml = dedent("""
            <problem>
            <p>Answer is B</p>
            <stringresponse answer="B">
                <textline size="20"/>
            </stringresponse>
            </problem>
        """)
        self.course_fixture.add_children(
            XBlockFixtureDesc('chapter', '1').add_children(
                XBlockFixtureDesc('sequential', '1.1').add_children(
                    XBlockFixtureDesc('vertical', '1.1.1'),
                    XBlockFixtureDesc('vertical', '1.1.2').add_children(
                        XBlockFixtureDesc('problem', 'Test Problem 1', data=problem1_xml),
                        XBlockFixtureDesc('problem', 'Test Problem 2', data=problem2_xml),
                    ),
                    XBlockFixtureDesc('vertical', '1.1.3').add_children(
                        XBlockFixtureDesc('html', 'Test HTML 1', data='<html>Test HTML 1</html>')
                    )
                ),
                XBlockFixtureDesc('sequential', '1.2').add_children(
                    XBlockFixtureDesc('vertical', '1.2.1').add_children(
                        XBlockFixtureDesc('problem', 'Test Problem 3')
                    ),
                    XBlockFixtureDesc('vertical', '1.2.2').add_children(
                        XBlockFixtureDesc('problem', 'Test Problem 4')
                    )
                )
            ),
            XBlockFixtureDesc('chapter', '2').add_children(
                XBlockFixtureDesc('sequential', '2.1').add_children(
                    XBlockFixtureDesc('vertical', '2.1.1').add_children(
                        XBlockFixtureDesc('html', 'Test HTML 2', data='<html>Test HTML 2</html>')
                    )
                ),
            )
        )
        self.course_fixture.install()

        self.course_outline_page = CourseOutlinePage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

        self.courseware_page = CoursewarePage(self.browser, self.course_id)

    def _switch_to_user(self, user_info, course_id=None, staff=None):
        self.logout()
        AutoAuthPage(
            self.browser,
            username=user_info['username'],
            password=user_info['password'],
            email=user_info['email'],
            course_id=course_id,
            staff=staff
        ).visit()
        return user_info

    def _set_progress_restriction(self):
        self._switch_to_user(SUPER_USER_INFO)

        DjangoAdminPage(self.browser).visit().click_add('ga_optional', 'courseoptionalconfiguration').input({
            'enabled': True,
            'key': 'progress-restriction-settings',
            'course_key': self.course_id,
        }).save()

    def _set_passing_mark(self, section_at, subsection_at, unit_at, passing_mark):
        self._set_progress_restriction()
        self._switch_to_user(self.user_info_staff, course_id=self.course_id, staff=True)

        self.course_outline_page.visit()
        self.course_outline_page.expand_all_subsections()
        unit = self.course_outline_page.section_at(section_at).subsection_at(subsection_at).unit_at(unit_at)
        modal = unit.edit()
        fields = modal.find_css('li.field-progress-restriction-passing-mark span.progress-restriction-percentage input')
        fields.fill(passing_mark)
        modal.save()

    def _get_sequential_tab_page(self, position):
        subsection_url = self.courseware_page.get_active_subsection_url()
        url_part_list = subsection_url.split('/')
        course_id = url_part_list[4]
        chapter_id = url_part_list[-3]
        subsection_id = url_part_list[-2]

        return CoursewareSequentialTabPage(
            self.browser,
            course_id=course_id,
            chapter=chapter_id,
            subsection=subsection_id,
            position=position
        )

    def test_accessibility_vertical_block(self):
        self._set_passing_mark(0, 0, 1, 100)

        # go to courseware
        self._switch_to_user(self.user_info, course_id=self.course_id, staff=False)

        self.courseware_page.visit()

        course_nav = CourseNavPage(self.browser)
        course_nav.go_to_section('1', '1.1')

        # go to next unit of the unit that is set passing mark
        # expecting not to be able to access
        tab3_page = self._get_sequential_tab_page(3).visit()
        self.assertIn('You need to make correct answers for the some problems in the before quiz.',
                      tab3_page.get_selected_tab_content())

        # send correct answer to 1/2
        tab2_page = self._get_sequential_tab_page(2).visit()
        problem_page = ProblemPage(self.browser)
        problem_page.fill_answer('A', 0)
        problem_page.click_check()

        # go to next unit of the unit that is set passing mark
        # expecting not to be able to access yet
        tab3_page.visit()
        self.assertIn('You need to make correct answers for the some problems in the before quiz.',
                      tab3_page.get_selected_tab_content())

        # send correct answer to 2/2
        tab2_page.visit()
        problem_page.fill_answer('B', 1)
        problem_page.click_check()

        # go to next unit of the unit that is set passing mark
        # expecting to be able to access
        tab3_page.visit()
        self.assertNotIn('You need to make correct answers for the some problems in the before quiz.',
                         tab3_page.get_selected_tab_content())
        self.assertIn('Test HTML 1',
                      tab3_page.get_selected_tab_content())

        # resend incorrect answer
        tab2_page.visit()
        problem_page.fill_answer('C', 1)
        problem_page.click_check()

        # go to next unit of the unit that is set passing mark
        # expecting to be able to access
        tab3_page.visit()
        self.assertNotIn('You need to make correct answers for the some problems in the before quiz.',
                         tab3_page.get_selected_tab_content())
        self.assertIn('Test HTML 1',
                      tab3_page.get_selected_tab_content())

    def test_can_access_previous_vertical_block(self):
        self._set_passing_mark(0, 0, 1, 100)

        # go to courseware
        self._switch_to_user(self.user_info, course_id=self.course_id, staff=False)

        self.courseware_page.visit()

        course_nav = CourseNavPage(self.browser)
        course_nav.go_to_section('1', '1.1')

        # go to previous unit of the unit that is set passing mark
        # expecting to be able to access
        tab_page = self._get_sequential_tab_page(0).visit()
        self.assertNotIn('You need to make correct answers for the some problems in the before quiz.',
                         tab_page.get_selected_tab_content())

    @ddt.data(
        ('1', '1.2', 'Test Problem 3'),
        ('2', '2.1', 'Test HTML 2')
    )
    @ddt.unpack
    def test_accessibility_sequential_block(self,
                                            access_chapter_name,
                                            access_sequential_name,
                                            unit_content):
        self._set_passing_mark(0, 0, 1, 100)

        # go to courseware
        self._switch_to_user(self.user_info, course_id=self.course_id, staff=False)

        self.courseware_page.visit()

        course_nav = CourseNavPage(self.browser)

        # go to the following subsections of the unit that is set passing mark
        # expecting not to be able to access
        course_nav.go_to_section(access_chapter_name, access_sequential_name)

        tab_page = self._get_sequential_tab_page(1).visit()
        self.assertIn('You need to make correct answers for the some problems in the before quiz.',
                      tab_page.get_selected_tab_content())

        # send correct answer
        course_nav.go_to_section('1', '1.1')
        self._get_sequential_tab_page(2).visit()
        problem_page = ProblemPage(self.browser)
        problem_page.fill_answer('A', 0)
        problem_page.fill_answer('B', 1)
        problem_page.click_check()

        # go to the following subsections of the unit that is set passing mark
        # expecting to be able to access
        course_nav.go_to_section(access_chapter_name, access_sequential_name)
        tab_page = self._get_sequential_tab_page(1).visit()
        self.assertNotIn('You need to make correct answers for the some problems in the before quiz.',
                         tab_page.get_selected_tab_content())
        self.assertIn(unit_content, tab_page.get_selected_tab_content())

    def test_display_restricted_on_sidebar(self):
        self._set_passing_mark(0, 0, 1, 100)

        # go to courseware
        self._switch_to_user(self.user_info, course_id=self.course_id, staff=False)

        self.courseware_page.visit()

        chapters = self.courseware_page.q(css='.course-index .accordion .course-navigation .chapter')
        self.assertEqual(len(chapters), 2)

        classes_of_chapters = chapters.attrs('class')
        self.assertNotIn('restricted-chapter', classes_of_chapters[0].split(' '))
        self.assertIn('restricted-chapter', classes_of_chapters[1].split(' '))

        sections = self.courseware_page.q(css='.course-index .accordion .course-navigation .chapter-content-container .chapter-menu .menu-item')
        self.assertEqual(len(sections), 3)

        classes_of_sections = sections.attrs('class')
        self.assertNotIn('restricted-section', classes_of_sections[0].split(' '))
        self.assertIn('restricted-section', classes_of_sections[1].split(' '))
        self.assertIn('restricted-section', classes_of_sections[2].split(' '))

        # send correct answer
        course_nav = CourseNavPage(self.browser)
        course_nav.go_to_section('1', '1.1')
        self._get_sequential_tab_page(2).visit()
        problem_page = ProblemPage(self.browser)
        problem_page.fill_answer('A', 0)
        problem_page.fill_answer('B', 1)
        problem_page.click_check()

        chapters = self.courseware_page.q(css='.course-index .accordion .course-navigation .chapter')
        self.assertEqual(len(chapters), 2)

        classes_of_chapters = chapters.attrs('class')
        self.assertNotIn('restricted-chapter', classes_of_chapters[0].split(' '))
        self.assertNotIn('restricted-chapter', classes_of_chapters[1].split(' '))

        sections = self.courseware_page.q(css='.course-index .accordion .course-navigation .chapter-content-container .chapter-menu .menu-item')
        self.assertEqual(len(sections), 3)

        classes_of_sections = sections.attrs('class')
        self.assertNotIn('restricted-section', classes_of_sections[0].split(' '))
        self.assertNotIn('restricted-section', classes_of_sections[1].split(' '))
        self.assertNotIn('restricted-section', classes_of_sections[2].split(' '))
