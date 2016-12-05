"""
Field overrides for ga-self-paced courses. This allows overriding due
dates for each block in the course.
"""
import logging

from openedx.core.djangoapps.ga_self_paced.api import get_base_date, get_individual_date
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from student.models import CourseEnrollment

from .access import has_access
from .field_overrides import FieldOverrideProvider

log = logging.getLogger(__name__)


class SelfPacedDateOverrideProvider(FieldOverrideProvider):
    """
    A concrete implementation of
    :class:`~courseware.field_overrides.FieldOverrideProvider` which allows for
    due dates to be overridden for self-paced courses.
    """
    def get(self, block, name, default):
        course_key = block.location.course_key
        if name == 'due':
            # Ignore due date in case of access by staff or no setting, otherwise return individual date.
            if has_access(self.user, 'staff', course_key) or not self._has_individual_due(block):
                return None
            else:
                enrollment = CourseEnrollment.get_enrollment(self.user, course_key)
                return get_individual_date(get_base_date(enrollment), {
                    'days': getattr(block, 'individual_due_days', 0),
                    'hours': getattr(block, 'individual_due_hours', 0),
                    'minutes': getattr(block, 'individual_due_minutes', 0),
                })
        if name == 'start' and block.category != 'course':
            # Ignore release date in case of access by staff or no setting, otherwise return individual date.
            if has_access(self.user, 'staff', course_key) or not self._has_individual_start(block):
                return None
            else:
                enrollment = CourseEnrollment.get_enrollment(self.user, course_key)
                return get_individual_date(get_base_date(enrollment), {
                    'days': getattr(block, 'individual_start_days', 0),
                    'hours': getattr(block, 'individual_start_hours', 0),
                    'minutes': getattr(block, 'individual_start_minutes', 0),
                })
        return default

    @classmethod
    def enabled_for(cls, course):
        """This provider is enabled for self-paced courses only."""
        return SelfPacedConfiguration.current().enabled and course.self_paced

    def _has_individual_due(self, block):
        return (
            getattr(block, 'individual_due_days', None) or
            getattr(block, 'individual_due_hours', None) or
            getattr(block, 'individual_due_minutes', None)
        )

    def _has_individual_start(self, block):
        return (
            getattr(block, 'individual_start_days', None) or
            getattr(block, 'individual_start_hours', None) or
            getattr(block, 'individual_start_minutes', None)
        )
