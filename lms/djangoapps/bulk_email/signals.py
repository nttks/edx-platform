from django.db.models.signals import post_save
from django.dispatch import receiver

from openedx.core.djangoapps.course_global.models import CourseGlobalSetting

from .models import Optout


@receiver(post_save, sender=CourseGlobalSetting)
def sync_optout_with_global_courses(sender, **kwargs):
    """
    To sync optout records of each all global courses.

    Why?
        Optout set on accout-settings page, not each courses on dashboard page.
        When you delete some global course, optout records of each global courses are same for ever.

    Attention !!!
        If you delete a global course or update to disable, optout records(deleted) are not deleted.

    Detail: #1089
    """
    global_course_ids = CourseGlobalSetting.all_course_id()
    if len(global_course_ids) > 1:
        for optout in Optout.objects.filter(course_id__in=global_course_ids).values('user').distinct():
            for course_id in global_course_ids:
                Optout.objects.get_or_create(user_id=optout['user'], course_id=course_id)
