"""
This module for tab for biz(has course_operation access).
"""
from django.utils.translation import ugettext_noop

from xmodule.tabs import CourseTab

from biz.djangoapps.ga_contract.models import ContractDetail
from biz.djangoapps.ga_manager.models import Manager


class ManagerTab(CourseTab):
    """
    Defines the Manager view type that is shown as a course tab.
    """

    type = "biz_manager"
    icon = 'fa fa-user-secret'
    title = ugettext_noop('BizManager')
    view_name = "biz:course_operation:dashboard"
    is_dynamic = True

    @classmethod
    def is_enabled(cls, course, user=None):
        """
        Returns true if the specified user has course_operation access.
        """
        if not user or not course:
            return False
        orgs = [m.org for m in Manager.get_managers(user) if m.can_handle_course_operation()]
        return orgs and course.id in [detail.course_id for detail in ContractDetail.find_enabled_by_contractors(orgs)]
