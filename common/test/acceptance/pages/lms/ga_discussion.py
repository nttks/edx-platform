from .discussion import DiscussionUserProfilePage as EdXDiscussionUserProfilePage


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
