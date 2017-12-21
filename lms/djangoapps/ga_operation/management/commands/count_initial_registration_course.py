import logging
import pytz
import traceback
from datetime import datetime

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import connection

log = logging.getLogger(__name__)
query_text = """
SELECT a.course_id, COUNT(a.course_id)
FROM student_courseenrollment a INNER JOIN (
    SELECT user_id, MIN(created) AS created
    FROM student_courseenrollment
    WHERE course_id NOT IN (SELECT course_id FROM course_global_courseglobalsetting WHERE global_enabled = 1) AND course_id LIKE '%gacco%'
    GROUP BY user_id
) b
ON a.user_id = b.user_id AND a.created = b.created
GROUP BY a.course_id;
"""


class Command(BaseCommand):
    """
    This command allows you to aggregate user's initial registration course.

    Usage: python manage.py lms --settings=aws count_initial_registration_course
    """
    help = 'Usage: count_initial_registration_course'

    def handle(self, *args, **options):
        body = None

        try:
            with connection.cursor() as cursor:
                cursor.execute(query_text)
                body = "\n".join(['"{0}",{1}'.format(*c) for c in cursor.fetchall()])
            log.info(body)
        except Exception as e:
            log.exception('Caught the exception: ' + type(e).__name__)
            body = traceback.format_exc()
        finally:
            send_mail(
                'Initial registration course daily report ({0:%Y/%m/%d})'.format(
                    pytz.timezone(settings.TIME_ZONE).localize(datetime.now()),
                ),
                body,
                settings.GA_OPERATION_EMAIL_SENDER_REGISTRATION_COURSE_DAILY_REPORT,
                settings.GA_OPERATION_CALLBACK_EMAIL_REGISTRATION_COURSE_DAILY_REPORT,
                fail_silently=False
            )
