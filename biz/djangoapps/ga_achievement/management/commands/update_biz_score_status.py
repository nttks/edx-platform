"""
Management command to generate a list of grade summary
for all biz students who registered any SPOC course.
"""
from collections import OrderedDict
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, make_option
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus
from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_contract.models import ContractDetail, AdditionalInfo
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting
from biz.djangoapps.util.decorators import handle_command_exception
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from certificates.models import CertificateStatuses, GeneratedCertificate
from courseware import grades, courses
from student.management.commands.get_grades import RequestMock
from student.models import UserProfile, UserStanding, CourseEnrollment

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Generate a list of grade summary for all biz students who registered any SPOC course.
    """
    help = """
    Usage: python manage.py lms --settings=aws update_biz_score_status [--debug] [<contract_id>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
    )

    @handle_command_exception(settings.BIZ_SET_SCORE_COMMAND_OUTPUT)
    def handle(self, *args, **options):
        # Note: BaseCommand translations are deactivated by default, so activate here
        translation.activate(settings.LANGUAGE_CODE)

        debug = options['debug']
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)

        if len(args) > 1:
            raise CommandError("This command requires one or no arguments: |<contract_id>|")

        contract_id = args[0] if len(args) > 0 else None
        if contract_id:
            contract_details = ContractDetail.find_enabled_by_contract_id(contract_id)
            if not contract_details:
                raise CommandError("The specified contract does not exist or is not active.")
        else:
            contract_details = ContractDetail.find_enabled()

        error_flag = False
        for contract_detail in contract_details:
            try:
                contract_id = contract_detail.contract_id
                course_key = contract_detail.course_id
                log.debug(u"Command update_biz_score_status is now processing [{}][{}]".format(
                    contract_id, unicode(course_key)))
                ScoreBatchStatus.save_for_started(contract_id, course_key)

                # Records
                records = []
                for contract_register in ContractRegister.find_input_and_register_by_contract(
                        contract_id).select_related('user__profile'):
                    user = contract_register.user
                    # Full Name
                    try:
                        user_profile = user.profile
                    except UserProfile.DoesNotExist:
                        user_profile = None
                    full_name = user_profile.name if user_profile else None

                    # Student Status
                    try:
                        # Note: Needs to be fixed in Dogwood because UserStanding.user is changed into OneToOneField
                        user_standing = user.standing.get()
                    except UserStanding.DoesNotExist:
                        user_standing = None
                    course_enrollment = CourseEnrollment.get_enrollment(user, course_key)
                    if user_standing and user_standing.account_status == UserStanding.ACCOUNT_DISABLED:
                        student_status = _(ScoreStore.FIELD_STUDENT_STATUS__DISABLED)
                    elif not course_enrollment:
                        student_status = _(ScoreStore.FIELD_STUDENT_STATUS__NOT_ENROLLED)
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
                    record[ScoreStore.FIELD_CONTRACT_ID] = contract_id
                    record[ScoreStore.FIELD_COURSE_ID] = unicode(course_key)
                    record[_(ScoreStore.FIELD_FULL_NAME)] = full_name
                    record[_(ScoreStore.FIELD_USERNAME)] = user.username
                    record[_(ScoreStore.FIELD_EMAIL)] = user.email
                    additional_infos = AdditionalInfo.find_by_contract_id(contract_id)
                    for additional_info in additional_infos:
                        record[additional_info.display_name] = AdditionalInfoSetting.get_value_by_display_name(
                            user, contract_id, additional_info.display_name)
                    record[_(ScoreStore.FIELD_STUDENT_STATUS)] = student_status
                    record[_(ScoreStore.FIELD_CERTIFICATE_STATUS)] = certificate_status
                    record[_(ScoreStore.FIELD_ENROLL_DATE)] = course_enrollment.created \
                        if course_enrollment else DEFAULT_DATETIME
                    record[_(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)] = generated_certificate.created_date \
                        if generated_certificate else DEFAULT_DATETIME
                    grade = get_grade(course_key, user)
                    for section in grade['section_breakdown']:
                        record[section['label']] = float('{:.2f}'.format(section['percent']))
                    record[_(ScoreStore.FIELD_TOTAL_SCORE)] = float('{:.2f}'.format(grade['percent']))
                    records.append(record)

                score_store = ScoreStore(contract_id, unicode(course_key))
                score_store.remove_documents()
                if records:
                    score_store.set_documents(records)
                    score_store.drop_indexes()
                    score_store.ensure_indexes()
                ScoreBatchStatus.save_for_finished(contract_id, course_key, len(records))

            except Exception as ex:
                error_flag = True
                log.error(u"Unexpected error occurred: {}".format(ex))
                ScoreBatchStatus.save_for_error(contract_id, course_key)

        if error_flag:
            raise CommandError("Error occurred while handling update_biz_score_status command.")


def get_grade(course_key, student):
    factory = RequestMock()
    request = factory.get('/')
    course = courses.get_course_by_id(course_key)

    return grades.grade(student, request, course)
