from .discussion import (
    DiscussionUserProfilePage as EdXDiscussionUserProfilePage,
    DiscussionTabHomePage as EdXDiscussionTabHomePage
)


class DiscussionUserProfilePage(EdXDiscussionUserProfilePage):

    def is_browser_on_page(self):
        return (
            self.q(css='section.discussion-user-threads[data-course-id="{}"]'.format(self.course_id)).present
            and
            self.q(css='section.user-profile div.sidebar-username').present
            and
            self.q(css='section.user-profile div.sidebar-username').text[0] == self.username
        )

    def exists_sidebar_username_link_element(self):
        return self.q(css='section.user-profile div.sidebar-username > a').present

class DiscussionTabHomePage(EdXDiscussionTabHomePage):

    def view_dialog_image_insert(self):
        self.q(css='#wmd-image-button-js-post-body-undefined').first.click()
        self.wait_for_element_visibility('div.wmd-prompt-dialog', "Prompt dialog visible")
        return self

    def exists_input_file_on_dialog(self):
        return self.q(css='div.wmd-prompt-dialog > form > input[type="file"]').present
