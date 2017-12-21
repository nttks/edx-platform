# -*- coding: utf-8 -*-
"""
Test helper functions and base classes.
"""
from .ga_helpers import GaccoTestMixin, SUPER_USER_INFO, GA_COURSE_SCORER_USER_INFO, GA_GLOBAL_COURSE_CREATOR_USER_INFO
from ..pages.lms.auto_auth import AutoAuthPage
from ..pages.lms.ga_instructor_dashboard import MembershipPageMemberListSection, InstructorDashboardPage


class GaccoTestRoleMixin(GaccoTestMixin):
    def add_course_role(self, course_id, role_name, member):
        self.switch_to_user(SUPER_USER_INFO)
        instructor_dashboard_page = InstructorDashboardPage(self.browser, course_id).visit()
        instructor_dashboard_page.select_membership()
        MembershipPageMemberListSection(self.browser).wait_for_page().add_role_by_display_name(role_name, member)
        self.logout()

    def auto_auth_with_ga_global_course_creator(self, course_id):
        # Auto-auth register for the course
        AutoAuthPage(
            self.browser,
            username=GA_GLOBAL_COURSE_CREATOR_USER_INFO['username'],
            password=GA_GLOBAL_COURSE_CREATOR_USER_INFO['password'],
            email=GA_GLOBAL_COURSE_CREATOR_USER_INFO['email'],
            course_id=course_id
        ).visit()
        return GA_GLOBAL_COURSE_CREATOR_USER_INFO

    def auto_auth_with_ga_course_scorer(self, course_id):
        self.add_course_role(course_id, 'Course Scorer', GA_COURSE_SCORER_USER_INFO['email'])
        AutoAuthPage(
            self.browser,
            username=GA_COURSE_SCORER_USER_INFO['username'],
            password=GA_COURSE_SCORER_USER_INFO['password'],
            email=GA_COURSE_SCORER_USER_INFO['email'],
            course_id=course_id
        ).visit()
        return GA_COURSE_SCORER_USER_INFO
