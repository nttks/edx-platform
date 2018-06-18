"""
Field overrides for ga-self-paced courses. This allows overriding due
dates for each block in the course.
"""
import logging

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from openedx.core.djangoapps.ga_self_paced.api import get_base_date, get_individual_date
from openedx.core.djangoapps.self_paced.models import SelfPacedConfiguration
from student.models import CourseEnrollment
from xmodule.course_metadata_utils import DEFAULT_START_DATE

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
            if has_access(self.user, 'staff', course_key):
                # Ignore due date in case of access by staff.
                return None
            elif self._has_individual_due(block):
                enrollment = CourseEnrollment.get_enrollment(self.user, course_key)
                individual_due_date = get_individual_date(get_base_date(enrollment), {
                    'days': getattr(block, 'individual_due_days', 0),
                    'hours': getattr(block, 'individual_due_hours', 0),
                    'minutes': getattr(block, 'individual_due_minutes', 0),
                })
                # If course end date is earlier than individual due date, then set course end date. #2479
                course_end_date = self_paced_api.get_course_end_date(enrollment)
                return individual_due_date if individual_due_date and individual_due_date < course_end_date else course_end_date
            else:
                # If individual due days are not set, then the due is the end of the course. See #1559
                return self._get_course_terminate_start(course_key)
        if name == 'start' and block.category != 'course':
            if has_access(self.user, 'staff', course_key):
                # Ignore release date in case of access by staff.
                return None
            elif self._has_individual_start(block):
                enrollment = CourseEnrollment.get_enrollment(self.user, course_key)
                return get_individual_date(get_base_date(enrollment), {
                    'days': getattr(block, 'individual_start_days', 0),
                    'hours': getattr(block, 'individual_start_hours', 0),
                    'minutes': getattr(block, 'individual_start_minutes', 0),
                })
            else:
                # If individual start days are not set, it is practically unpublished. See #1559
                return DEFAULT_START_DATE
        return default

    @classmethod
    def enabled_for(cls, course):
        """This provider is enabled for self-paced courses only."""
        return SelfPacedConfiguration.current().enabled and course.self_paced

    def _has_individual_due(self, block):
        return (
            getattr(block, 'individual_due_days', None) is not None or
            getattr(block, 'individual_due_hours', None) is not None or
            getattr(block, 'individual_due_minutes', None) is not None
        )

    def _has_individual_start(self, block):
        return (
            getattr(block, 'individual_start_days', None) is not None or
            getattr(block, 'individual_start_hours', None) is not None or
            getattr(block, 'individual_start_minutes', None) is not None
        )

    def _get_course_terminate_start(self, course_key):
        overview = CourseOverview.get_from_id(course_key)
        return overview.extra and overview.extra.terminate_start
