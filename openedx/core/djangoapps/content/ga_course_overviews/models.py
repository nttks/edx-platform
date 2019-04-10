"""
Declaration of CourseOverview model for gacco
"""
from datetime import datetime

from django.db import models
from django.utils.timezone import UTC

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.courses import custom_logo_url


class CourseOverviewExtra(models.Model):
    """
    Model for storing and caching extra information about a course for gacco.
    """

    class Meta(object):
        app_label = 'ga_course_overviews'

    course_overview = models.OneToOneField(CourseOverview, db_index=True)

    is_course_hidden = models.BooleanField(default=False)
    terminate_start = models.DateTimeField(null=True)
    is_status_managed = models.BooleanField(default=False)
    course_category = models.TextField(default="", null=True)
    course_category_order = models.IntegerField(null=True)
    course_category2 = models.TextField(default="", null=True)
    course_category_order2 = models.IntegerField(null=True)
    course_order = models.IntegerField(null=True)

    # for face-to-face course
    is_f2f_course = models.BooleanField(default=False)
    is_f2f_course_sell = models.BooleanField(default=False)

    # for self-paced
    self_paced = models.BooleanField(default=False)
    individual_end_days = models.IntegerField(null=True)
    individual_end_hours = models.IntegerField(null=True)
    individual_end_minutes = models.IntegerField(null=True)
    custom_logo = models.TextField(blank=True, default="")

    @classmethod
    def create(cls, course, overview):
        cls(
            course_overview=overview,
            is_course_hidden=course.is_course_hidden,
            terminate_start=course.terminate_start,
            is_status_managed=course.is_status_managed,
            course_category=''.join(course.course_category or []),
            course_category_order=course.course_category_order,
            course_category2=course.course_category2,
            course_category_order2=course.course_category_order2,
            course_order=course.course_order,
            is_f2f_course=course.is_f2f_course,
            is_f2f_course_sell=course.is_f2f_course_sell,
            self_paced=course.self_paced,
            individual_end_days=course.individual_end_days,
            individual_end_hours=course.individual_end_hours,
            individual_end_minutes=course.individual_end_minutes,
            custom_logo=custom_logo_url(course)
        ).save()

    @property
    def has_terminated(self):
        """
        Returns True if the current time is after the specified course terminated date.
        Otherwise returns False. (Also returns False if there is no terminated date specified.)
        """
        # backward compatibility
        if self.is_course_hidden:
            return True

        if self.terminate_start is None:
            return False

        return datetime.now(UTC()) > self.terminate_start

    @property
    def has_individual_end(self):
        return (
            self.individual_end_days is not None or
            self.individual_end_hours is not None or
            self.individual_end_minutes is not None
        )
