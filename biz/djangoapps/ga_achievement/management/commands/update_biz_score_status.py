"""
Management command to generate a list of grade summary
for all biz students who registered any SPOC course.
"""
from collections import OrderedDict
import logging
from optparse import make_option
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus
from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_contract.models import Contract, AdditionalInfo
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting
from biz.djangoapps.util.decorators import handle_command_exception
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from certificates.models import CertificateStatuses, GeneratedCertificate
from courseware import grades, courses
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from student.management.commands.get_grades import RequestMock
from student.models import UserStanding, CourseEnrollment
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


class CourseDoesNotExist(Exception):
    """
    This exception is raised in the case where None is returned from the modulestore
    """
    pass


class Command(BaseCommand):
    """
    Generate a list of grade summary for all biz students who registered any SPOC course.
    """
    help = """
    Usage: python manage.py lms --settings=aws update_biz_score_status [--debug] [--force] [--excludes=<exclude_ids>|<contract_id>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
        make_option('-f', '--force',
                    default=False,
                    action='store_true',
                    help='Force to start process even if today\'s batch status exists'),
        make_option('--excludes',
                    default=None,
                    action='store',
                    help='Specify contract ids to exclude as comma-delimited integers (like 1 or 1,2)'),
    )

    @handle_command_exception(settings.BIZ_SET_SCORE_COMMAND_OUTPUT)
    def handle(self, *args, **options):
        # Note: BaseCommand translations are deactivated by default, so activate here
        translation.activate(settings.LANGUAGE_CODE)

        debug = options.get('debug')
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)
        force = options.get('force')
        exclude_ids = options.get('excludes') or []
        if exclude_ids:
            try:
                exclude_ids = map(int, exclude_ids.split(','))
            except ValueError:
                raise CommandError("excludes should be specified as comma-delimited integers (like 1 or 1,2).")
        log.debug(u"exclude_ids={}".format(exclude_ids))

        if len(args) > 1:
            raise CommandError("This command requires one or no arguments: |<contract_id>|")

        contract_id = args[0] if len(args) > 0 else None
        if contract_id:
            if exclude_ids:
                raise CommandError("Cannot specify exclude_ids and contract_id at the same time.")
            try:
                contracts = [Contract.objects.enabled().get(pk=contract_id)]
            except Contract.DoesNotExist:
                raise CommandError("The specified contract does not exist or is not active.")
        else:
            contracts = Contract.objects.enabled().all().exclude(id__in=exclude_ids).order_by('id')
        log.debug(u"contract_ids=[{}]".format(','.join([str(contract.id) for contract in contracts])))

        error_flag = False
        for contract in contracts:
            # Check if batch process for the contract has not yet started today
            if ScoreBatchStatus.exists_today(contract.id):
                if force:
                    log.warning(
                        u"Command update_biz_score_status for contract({}) has already started today, but force to start.".format(
                            contract.id))
                else:
                    log.warning(
                        u"Command update_biz_score_status for contract({}) has already started today, so skip.".format(
                            contract.id))
                    continue

            for contract_detail in contract.details.all():
                try:
                    course_key = contract_detail.course_id
                    log.info(
                        u"Command update_biz_score_status for contract({}) and course({}) is now processing...".format(
                            contract.id, unicode(course_key)))
                    ScoreBatchStatus.save_for_started(contract.id, course_key)

                    # Check if course exists in modulestore
                    course = modulestore().get_course(course_key)
                    if not course:
                        raise CourseDoesNotExist()

                    # Records
                    records = []
                    for contract_register in ContractRegister.find_input_and_register_by_contract(
                            contract.id).select_related('user__standing', 'user__profile'):
                        user = contract_register.user
                        # Student Status
                        course_enrollment = CourseEnrollment.get_enrollment(user, course_key)
                        if hasattr(user, 'standing') and user.standing \
                            and user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                            student_status = _(ScoreStore.FIELD_STUDENT_STATUS__DISABLED)
                        elif not course_enrollment:
                            student_status = _(ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED)
                        elif self_paced_api.is_course_closed(course_enrollment):
                            student_status = _(ScoreStore.FIELD_STUDENT_STATUS__EXPIRED)
                        elif course_enrollment.is_active:
                            student_status = _(ScoreStore.FIELD_STUDENT_STATUS__ENROLLED)
                        else:
                            student_status = _(ScoreStore.FIELD_STUDENT_STATUS__UNENROLLED)

                        # Certificate Status
                        generated_certificate = GeneratedCertificate.certificate_for_student(user, course_key)
                        if generated_certificate and generated_certificate.status == CertificateStatuses.downloadable:
                            certificate_status = _(ScoreStore.FIELD_CERTIFICATE_STATUS__DOWNLOADABLE)
                        else:
                            certificate_status = _(ScoreStore.FIELD_CERTIFICATE_STATUS__UNPUBLISHED)

                        # Records
                        record = OrderedDict()
                        record[ScoreStore.FIELD_CONTRACT_ID] = contract.id
                        record[ScoreStore.FIELD_COURSE_ID] = unicode(course_key)
                        if hasattr(contract_register.user, 'bizuser'):
                            # Only in the case of a contract using login code, setting processing of data is performed.
                            record[_(ScoreStore.FIELD_LOGIN_CODE)] = contract_register.user.bizuser.login_code
                        record[_(ScoreStore.FIELD_FULL_NAME)] = user.profile.name \
                            if hasattr(user, 'profile') and user.profile else None
                        record[_(ScoreStore.FIELD_USERNAME)] = user.username
                        record[_(ScoreStore.FIELD_EMAIL)] = user.email
                        additional_infos = AdditionalInfo.find_by_contract_id(contract.id)
                        for additional_info in additional_infos:
                            record[additional_info.display_name] = AdditionalInfoSetting.get_value_by_display_name(
                                user, contract.id, additional_info.display_name)
                        record[_(ScoreStore.FIELD_STUDENT_STATUS)] = student_status
                        record[_(ScoreStore.FIELD_CERTIFICATE_STATUS)] = certificate_status
                        record[_(ScoreStore.FIELD_ENROLL_DATE)] = course_enrollment.created \
                            if course_enrollment else DEFAULT_DATETIME
                        # Add Expire Date only if course is self-paced
                        if course.self_paced:
                            record[_(ScoreStore.FIELD_EXPIRE_DATE)] = self_paced_api.get_course_end_date(course_enrollment) or DEFAULT_DATETIME
                        record[_(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)] = generated_certificate.created_date \
                            if generated_certificate else DEFAULT_DATETIME
                        start = time.clock()
                        grade = get_grade(course_key, user)
                        end = time.clock()
                        log.debug(u"Processing time for get_grade() ... {:.2f}s".format(end - start))
                        for section in grade['section_breakdown']:
                            record[section['label']] = float('{:.2f}'.format(section['percent']))
                        record[_(ScoreStore.FIELD_TOTAL_SCORE)] = float('{:.2f}'.format(grade['percent']))
                        records.append(record)

                    score_store = ScoreStore(contract.id, unicode(course_key))
                    score_store.remove_documents()
                    if records:
                        score_store.set_documents(records)
                        score_store.drop_indexes()
                        score_store.ensure_indexes()
                    ScoreBatchStatus.save_for_finished(contract.id, course_key, len(records))

                except CourseDoesNotExist:
                    log.warning(u"This course does not exist in modulestore. course_id={}".format(unicode(course_key)))
                    ScoreBatchStatus.save_for_error(contract.id, course_key)
                except Exception as ex:
                    error_flag = True
                    log.error(u"Unexpected error occurred: {}".format(ex))
                    ScoreBatchStatus.save_for_error(contract.id, course_key)

            if error_flag:
                raise CommandError("Error occurred while handling update_biz_score_status command.")


def get_grade(course_key, student):
    factory = RequestMock()
    request = factory.get('/')
    course = courses.get_course_by_id(course_key)

    return grades.grade(student, request, course)
