"""
Management command to generate a list of grades for
all students that are enrolled in a course.
"""
from collections import OrderedDict
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus
from biz.djangoapps.ga_achievement.score_store import (
    ScoreStore, SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID,
    SCORE_STORE_FIELD_NAME, SCORE_STORE_FIELD_USERNAME, SCORE_STORE_FIELD_EMAIL, SCORE_STORE_FIELD_STUDENT_STATUS,
    SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED,
    SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED, SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS, SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE,
    SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED, SCORE_STORE_FIELD_ENROLL_DATE,
    SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE, SCORE_STORE_FIELD_TOTAL_SCORE,
)
from biz.djangoapps.ga_contract.models import ContractDetail
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting
from biz.djangoapps.util.decorators import handle_command_exception
from biz.djangoapps.util.mongo_utils import DEFAULT_DATETIME
from certificates.models import CertificateStatuses, GeneratedCertificate
from courseware import grades, courses
from student.management.commands.get_grades import RequestMock
from student.models import UserProfile, UserStanding, CourseEnrollment

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Generate a list of grades for all biz students
    that are enrolled in a course.

    Example:
      python manage.py lms --settings=aws update_biz_score_status
    """

    @handle_command_exception(settings.BIZ_SET_SCORE_COMMAND_OUTPUT)
    def handle(self, *args, **options):
        translation.activate(settings.LANGUAGE_CODE)
        contract_detail_list = ContractDetail.find_enabled().select_related()
        error_flag = False

        for contract_detail in contract_detail_list:
            try:
                score_list = []
                contract_register_list = ContractRegister.find_registered_by_contract(contract_detail.contract_id)

                contract_id = contract_detail.contract_id
                course_id = contract_detail.course_id
                score_store = ScoreStore(contract_id, unicode(course_id))

                ScoreBatchStatus.save_for_started(contract_id, course_id)
                for contract_register in contract_register_list:
                    user = contract_register.user
                    try:
                        user_profile = UserProfile.objects.get(user=user)
                    except UserProfile.DoesNotExist:
                        user_profile = None
                    try:
                        user_standing = UserStanding.objects.get(user=user)
                    except UserStanding.DoesNotExist:
                        user_standing = None
                    course_enrollment = CourseEnrollment.get_enrollment(user, course_id)
                    generated_certificate = GeneratedCertificate.certificate_for_student(user, course_id)
                    additional_info_setting_list = AdditionalInfoSetting.find_by_user_and_contract(user, contract_id)
                    grade = get_grade(course_id, user)

                    # Student Status
                    if user_standing and user_standing.account_status == UserStanding.ACCOUNT_DISABLED:
                        student_status = _(SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED)
                    elif not course_enrollment:
                        student_status = _(SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED)
                    elif course_enrollment.is_active:
                        student_status = _(SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED)
                    else:
                        student_status = _(SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED)
                    # Certificate Status
                    if generated_certificate and generated_certificate.status == CertificateStatuses.downloadable:
                        certificate_status = _(SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE)
                    else:
                        certificate_status = _(SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED)

                    score = OrderedDict()
                    score[SCORE_STORE_FIELD_CONTRACT_ID] = contract_id
                    score[SCORE_STORE_FIELD_COURSE_ID] = unicode(course_id)
                    score[_(SCORE_STORE_FIELD_NAME)] = user_profile.name if user_profile else None
                    score[_(SCORE_STORE_FIELD_USERNAME)] = user.username
                    score[_(SCORE_STORE_FIELD_EMAIL)] = user.email
                    for additional_info_setting in additional_info_setting_list:
                        score[additional_info_setting.display_name] = additional_info_setting.value
                    score[_(SCORE_STORE_FIELD_STUDENT_STATUS)] = student_status
                    score[_(SCORE_STORE_FIELD_CERTIFICATE_STATUS)] = certificate_status
                    score[_(SCORE_STORE_FIELD_ENROLL_DATE)] = course_enrollment.created \
                        if course_enrollment else DEFAULT_DATETIME
                    score[_(SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE)] = generated_certificate.created_date \
                        if generated_certificate else DEFAULT_DATETIME
                    for section in grade['section_breakdown']:
                        score[section['label']] = float('{:.2f}'.format(section['percent']))
                    score[_(SCORE_STORE_FIELD_TOTAL_SCORE)] = float('{:.2f}'.format(grade['percent']))
                    score_list.append(score)

                score_store.remove_documents()
                if score_list:
                    score_store.set_documents(score_list)
                    score_store.drop_indexes()
                    score_store.ensure_indexes()
                ScoreBatchStatus.save_for_finished(contract_id, course_id, len(score_list))

            except Exception as ex:
                log.error('Unexpected error: %s', ex)
                ScoreBatchStatus.save_for_error(contract_id, course_id)
                error_flag = True

        if error_flag:
            raise CommandError("Error occurred while handling update_biz_score_status command.")


def get_grade(course_id, student):
    factory = RequestMock()
    request = factory.get('/')
    course = courses.get_course_by_id(course_id)

    return grades.grade(student, request, course)
