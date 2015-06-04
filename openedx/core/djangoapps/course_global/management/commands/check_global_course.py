from django.core.management.base import BaseCommand

from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from openedx.core.djangoapps.course_global.management.commands import users_unenrolled_in


class Command(BaseCommand):
    """
    Show global course and status.
    """

    def handle(self, *args, **options):
        for global_course_id in CourseGlobalSetting.all_course_id():
            unenrolled_count = users_unenrolled_in(global_course_id).count()
            if unenrolled_count == 0:
                status = "All of active users are enrolled"
            else:
                status = "{} users are not enrolled".format(unenrolled_count)
            print "{} - {}".format(global_course_id.to_deprecated_string(), status)
