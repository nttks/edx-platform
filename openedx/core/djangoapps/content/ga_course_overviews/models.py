"""
Declaration of CourseOverview model for gacco
"""
from django.db import models

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


class CourseOverviewExtra(models.Model):
    """
    Model for storing and caching extra information about a course for gacco.
    """

    class Meta(object):
        app_label = 'ga_course_overviews'

    course_overview = models.OneToOneField(CourseOverview, db_index=True)

    has_terminated = models.BooleanField(default=False)

    # for face-to-face course
    is_f2f_course = models.BooleanField(default=False)
    is_f2f_course_sell = models.BooleanField(default=False)

    @classmethod
    def create(cls, course, overview):
        cls(
            course_overview=overview,
            has_terminated=course.has_terminated(),
            is_f2f_course=course.is_f2f_course,
            is_f2f_course_sell=course.is_f2f_course_sell
        ).save()
