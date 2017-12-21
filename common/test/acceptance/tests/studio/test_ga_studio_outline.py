"""
Acceptance tests for studio related to the outline page.
"""
import bok_choy.browser
import ddt

from base_studio_test import StudioCourseTest
from ..ga_helpers import GaccoTestMixin, SUPER_USER_INFO
from ...fixtures.course import CourseFixture, XBlockFixtureDesc
from ...pages.lms.ga_django_admin import DjangoAdminPage
from ...pages.studio.ga_overview import CourseOutlinePage


@ddt.ddt
class SettingProgressRestrictionTest(StudioCourseTest, GaccoTestMixin):

    def setUp(self):
        super(SettingProgressRestrictionTest, self).setUp()

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
        self.course_fixture.add_children(
            XBlockFixtureDesc('chapter', '1').add_children(
                XBlockFixtureDesc('sequential', '1.1').add_children(
                    XBlockFixtureDesc('vertical', '1.1.1'),
                    XBlockFixtureDesc('vertical', '1.1.2')
                ),
                XBlockFixtureDesc('sequential', '1.2').add_children(
                    XBlockFixtureDesc('vertical', '1.2.1'),
                    XBlockFixtureDesc('vertical', '1.2.2')
                )
            ),
            XBlockFixtureDesc('chapter', '2').add_children(
                XBlockFixtureDesc('sequential', '2.1').add_children(
                    XBlockFixtureDesc('vertical', '2.1.1'),
                )
            )
        )
        self.course_fixture.install()

        self.user = self.course_fixture.user
        self.log_in(self.user, True)

        self.course_outline_page = CourseOutlinePage(
            self.browser,
            self.course_info['org'],
            self.course_info['number'],
            self.course_info['run']
        )

    def _set_progress_restriction(self):
        self.switch_to_user(SUPER_USER_INFO)

        DjangoAdminPage(self.browser).visit().click_add('ga_optional', 'courseoptionalconfiguration').input({
            'enabled': True,
            'key': 'progress-restriction-settings',
            'course_key': self.course_id,
        }).save()

    @ddt.data(
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (0, 1, 1),
        (1, 0, 0),
    )
    @ddt.unpack
    def test_show_settings_form_for_passing_mark(self,
                                                 section_at,
                                                 subsection_at,
                                                 unit_at):
        """
        test for course with setting "progress-restriction-settings"
        """
        self._set_progress_restriction()
        self.course_outline_page.visit()
        self.course_outline_page.expand_all_subsections()
        unit = self.course_outline_page.section_at(section_at).subsection_at(subsection_at).unit_at(unit_at)
        modal = unit.edit()
        bok_choy.browser.save_screenshot(self.browser, 'show_settings_form_for_passing_mark')
        self.assertTrue('Passing Mark' in modal.find_css('.modal-section-title').text)

    @ddt.data(
        (0, 0, 0),
        (0, 0, 1),
        (0, 1, 0),
        (0, 1, 1),
        (1, 0, 0),
    )
    @ddt.unpack
    def test_does_not_show_settings_form_for_passing_mark(self,
                                                          section_at,
                                                          subsection_at,
                                                          unit_at):
        """
        test for course without setting "progress-restriction-settings"
        """
        self.course_outline_page.visit()
        self.course_outline_page.expand_all_subsections()
        unit = self.course_outline_page.section_at(section_at).subsection_at(subsection_at).unit_at(unit_at)
        modal = unit.edit()
        self.assertFalse('Passing Mark' in modal.find_css('.modal-section-title').text)

    @ddt.data(
        '-1',
        '101',
        'abcde',
    )
    def test_validate_input_for_passing_mark(self, input_value):
        """
        test invalid input for passing mark"
        """
        self._set_progress_restriction()
        self.course_outline_page.visit()
        self.course_outline_page.expand_all_subsections()
        unit = self.course_outline_page.section_at(0).subsection_at(0).unit_at(0)
        modal = unit.edit()
        self.assertEqual(u'', modal.find_css('#progress-restriction-passing-mark-error-message').text[0])
        modal.find_css('#progress-restriction-passing-mark').fill(input_value)
        modal.save()
        self.assertEqual(u'Please enter an integer between 0 and 100.',
                         modal.find_css('#progress-restriction-passing-mark-error-message').text[0])
