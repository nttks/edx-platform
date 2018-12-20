"""
Management command to unregister students with masked email.
"""
import logging
from optparse import make_option

from django.core.management.base import BaseCommand

from biz.djangoapps.ga_contract.models import ContractDetail
from biz.djangoapps.ga_invitation.models import (ContractRegister, UNREGISTER_INVITATION_CODE)
from student.models import CourseEnrollment

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Unregister a student of masked user.

    Example:
      python manage.py lms --settings=aws unregister_masked_user [--debug]
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
        log.info(u"unregister_masked_user command start {}".format('(dry run)' if debug else ''))
        # find users who are masked, which don't have an @ in the email, and unenroll from courses
        registers = ContractRegister.objects.exclude(user__email__contains='@').exclude(
            status=UNREGISTER_INVITATION_CODE).order_by('user__username')
        course_ids = [d.course_id for d in ContractDetail.objects.all()]

        # debug output for comparison with sql output
        if debug:
            register_user_set = set()
            log.debug(u"--------------debug target output (start)--------------")
            log.debug(u"{}\t{}".format('username', 'course_id'))
            for register in registers:
                if register.user in register_user_set:
                    continue
                else:
                    register_user_set.add(register.user)
                    for enrollment in CourseEnrollment.enrollments_for_user(register.user).filter(
                            course_id__in=course_ids).order_by('course_id'):
                        log.debug(u"{}\t{}".format(register.user.username, enrollment.course_id))
            log.debug(u"--------------debug target output (finished)--------------")
        else:
            # do unregister and unenroll if not debug
            register_user_set = set()
            for register in registers:
                if(register.user in register_user_set):
                    continue
                else:
                    register_user_set.add(register.user)
                    log.info(u"unregistering [start]... register.user.username:{}, register.user.email:{}".format(
                        register.user.username, register.user.email))
                    register.status = UNREGISTER_INVITATION_CODE
                    register.save()
                    for enrollment in CourseEnrollment.enrollments_for_user(register.user).filter(
                            course_id__in=course_ids).order_by('course_id'):
                        log.info(u"unenrolling ... username:{}, course_id:{}".format(register.user.username,
                                                                                     enrollment.course_id))
                        CourseEnrollment.unenroll(enrollment.user, enrollment.course_id)
                    log.info(u"unregistering [finished]... register.user.username:{}, register.user.email:{} ".format(
                        register.user.username, register.user.email))
            if not register_user_set:
                log.warn(u"unregister_masked_user command target not found.")

        log.info(u"unregister_masked_user command finished {}".format('(dry run)' if debug else ''))
