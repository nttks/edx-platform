"""
Course navigation page object
"""

from .course_nav import CourseNavPage as EdXCourseNavPage


class CourseNavPage(EdXCourseNavPage):
    """
    Navigate sections and sequences in the courseware.

    Note: Override `CourseNavPage` for the following reason.
        CSS selector of `nav>div.chapter` differs according to the viewport when gacco-theme is applied.
        So, we changed it as follows:
        (PC)     : #accordion>nav>div.chapter
        (Mobile) : #modal-accordion>nav>div.chapter
    """

    def go_to_section(self, section_title, subsection_title):
        """
        Go to the section in the courseware.
        Every section must have at least one subsection, so specify
        both the section and subsection title.

        Example:
            go_to_section("Week 1", "Lesson 1")
        """

        # For test stability, disable JQuery animations (opening / closing menus)
        self.browser.execute_script("jQuery.fx.off = true;")

        # Get the section by index
        try:
            sec_index = self._section_titles().index(section_title)
        except ValueError:
            self.warning("Could not find section '{0}'".format(section_title))
            return

        # Click the section to ensure it's open (no harm in clicking twice if it's already open)
        # Add one to convert from list index to CSS index
        section_css = '#accordion>nav>div.chapter:nth-of-type({0})>h3>a'.format(sec_index + 1)
        self.q(css=section_css).first.click()

        # Get the subsection by index
        try:
            subsec_index = self._subsection_titles(sec_index + 1).index(subsection_title)
        except ValueError:
            msg = "Could not find subsection '{0}' in section '{1}'".format(subsection_title, section_title)
            self.warning(msg)
            return

        # Convert list indices (start at zero) to CSS indices (start at 1)
        subsection_css = "#accordion>nav>div.chapter:nth-of-type({0})>ul>li:nth-of-type({1})>a".format(
            sec_index + 1, subsec_index + 1
        )

        # Click the subsection and ensure that the page finishes reloading
        self.q(css=subsection_css).first.click()
        self._on_section_promise(section_title, subsection_title).fulfill()

    def _section_titles(self):
        """
        Return a list of all section titles on the page.
        """
        chapter_css = '#accordion > nav > div.chapter > h3 > a'
        return self.q(css=chapter_css).map(lambda el: el.text.strip()).results

    def _subsection_titles(self, section_index):
        """
        Return a list of all subsection titles on the page
        for the section at index `section_index` (starts at 1).
        """
        # Retrieve the subsection title for the section
        # Add one to the list index to get the CSS index, which starts at one
        subsection_css = '#accordion>nav>div.chapter:nth-of-type({0})>ul>li>a>p:nth-of-type(1)'.format(section_index)

        # If the element is visible, we can get its text directly
        # Otherwise, we need to get the HTML
        # It *would* make sense to always get the HTML, but unfortunately
        # the open tab has some child <span> tags that we don't want.
        return self.q(
            css=subsection_css
        ).map(
            lambda el: el.text.strip().split('\n')[0] if el.is_displayed() else el.get_attribute('innerHTML').strip()
        ).results

    def _is_on_section(self, section_title, subsection_title):
        """
        Return a boolean indicating whether the user is on the section and subsection
        with the specified titles.

        This assumes that the currently expanded section is the one we're on
        That's true right after we click the section/subsection, but not true in general
        (the user could go to a section, then expand another tab).
        """
        current_section_list = self.q(css='#accordion>nav>div.chapter.is-open>h3>a').text
        current_subsection_list = self.q(css='#accordion>nav>div.chapter.is-open li.active>a>p').text

        if len(current_section_list) == 0:
            self.warning("Could not find the current section")
            return False

        elif len(current_subsection_list) == 0:
            self.warning("Could not find current subsection")
            return False

        else:
            return (
                current_section_list[0].strip() == section_title and
                current_subsection_list[0].strip().split('\n')[0] == subsection_title
            )
