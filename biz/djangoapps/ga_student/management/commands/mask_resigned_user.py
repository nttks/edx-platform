"""
Management command to mask users who already resigned.
"""

import logging
from optparse import make_option

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from biz.djangoapps.util import mask_utils, datetime_utils
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from student.models import Registration, UserStanding

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Mask users who already resigned.
    """
    help = """
    Usage: python manage.py lms --settings=aws mask_resigned_user [--debug]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
    )

    def handle(self, *args, **options):
        debug = options.get('debug')
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)
        log.info(u"Command mask_resigned_user started at {}.".format(datetime_utils.timezone_now()))

        mask_users = User.objects.filter(
            email__contains='@',  # Do not mask users who have already masked by biz (#1908)
            standing__account_status=UserStanding.ACCOUNT_DISABLED
        ).order_by('username')

        # debug output for comparison with sql output
        if debug:
            log.debug(u"--------------debug target output (start)--------------")
            log.debug('userid,username,email')
            for user in mask_users:
                log.debug(','.join([str(user.id), user.username, user.email]))
            log.debug(u"--------------debug target output (finished)--------------")
        else:
            failed_users = []

            for user in mask_users:
                log.info(u"Masked start user_id, user_name : {}, {}.".format(user.id, user.username))
                try:
                    with transaction.atomic():
                        mask_utils.disable_all_additional_info(user)
                        mask_utils.disable_user_info(user)
                        Registration.objects.get(user=user).update_masked()
                except:
                    log.exception(u"Masked failed user_id, user_name : {}, {}.".format(user.id, user.username))
                    failed_users.append(str(user.id) + '-' + user.username)
                else:
                    log.info(u"Masked success user_id, user_name : {}, {}.".format(user.id, user.username))

            if failed_users:
                log.error(u"Masked failed users : {}".format(failed_users))

        log.info(u"Command mask_user finished at {}.".format(datetime_utils.timezone_now()))
