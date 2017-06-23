"""
Management command to mask for users whose activation key has expired.
"""

import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from biz.djangoapps.util import mask_utils, datetime_utils
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from student.models import Registration

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Mask for users whose activation key has expired 
    """
    help = """
    Usage: python manage.py lms --settings=aws mask_user [--debug]
    """

    def handle(self, *args, **options):
        log.info(u"Command mask_user started at {}.".format(datetime_utils.timezone_now()))

        min_datetime, _ = datetime_utils.min_and_max_of_date(days_after=-settings.INTERVAL_DAYS_TO_MASK_UNACTIVATED_USER)
        mask_users = User.objects.filter(
            is_active=False,
            email__contains='@',  # Do not mask users who have already masked by biz (#1908)
            registration__masked=False,
            registration__modified__isnull=False,
            registration__modified__lt=min_datetime,
        )
        global_courses_ids = set(CourseGlobalSetting.all_course_id())

        failed_user_ids = []

        for user in mask_users:
            log.info(u"Masked start user_id : {}.".format(user.id))
            try:
                with transaction.atomic():
                    mask_utils.optout_receiving_global_course_emails(user, global_courses_ids)
                    mask_utils.mask_name(user)
                    mask_utils.mask_email(user)
                    mask_utils.disconnect_third_party_auth(user)
                    Registration.objects.get(user=user).update_masked()
            except:
                log.exception(u"Masked failed user_id : {}.".format(user.id))
                failed_user_ids.append(user.id)
            else:
                log.info(u"Masked success user_id : {}.".format(user.id))

        if failed_user_ids:
            log.error(u"Masked failed user_ids : {}".format(failed_user_ids))

        log.info(u"Command mask_user finished at {}.".format(datetime_utils.timezone_now()))
