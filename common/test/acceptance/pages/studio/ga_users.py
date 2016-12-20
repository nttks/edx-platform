"""
Page classes to test either the Course Team page or the Library Team page.
"""
from .users import CourseTeamPage as EdXCourseTeamPage


class CourseTeamPage(EdXCourseTeamPage):

    def add_course_staff(self, email):
        self.add_user_to_course(email)
        self.wait_until_no_loading_indicator()
        return self

    def add_course_admin(self, email):
        if not self.has_user(email):
            self.add_course_staff(email)
        self.get_user(email).click_promote()
        self.wait_until_no_loading_indicator()
        return self

    def has_user(self, email):
        return bool([user for user in self.users if user.email == email])
