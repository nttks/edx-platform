from django.db import models

from xmodule_django.models import CourseKeyField


class CourseGlobalSetting(models.Model):
    """
    This model represents settings of global course.
    The Global course is course that all of the user to enroll.
    """
    course_id = CourseKeyField(max_length=255, db_index=True, unique=True)
    global_enabled = models.BooleanField(default=True)

    @classmethod
    def all_global_settings(cls):
        """
        Returns all of available global settings.
        """
        return CourseGlobalSetting.objects.filter(global_enabled=True)

    @classmethod
    def all_course_id(cls):
        """
        Returns all of available global course id.
        """
        return [global_setting.course_id for global_setting in cls.all_global_settings()]

    def __unicode__(self):
        not_global_en = "Not "
        if self.global_enabled:
            not_global_en = ""
        return u"Course '{}': Global {}Enabled".format(self.course_id.to_deprecated_string(), not_global_en)
