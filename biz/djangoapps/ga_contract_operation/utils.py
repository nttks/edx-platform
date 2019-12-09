from collections import defaultdict

from django.utils.translation import ugettext as _
from biz.djangoapps.ga_contract.models import ContractDetail
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, UNREGISTER_INVITATION_CODE
from biz.djangoapps.util import mask_utils
from biz.djangoapps.util.access_utils import has_staff_access

from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from student.models import CourseEnrollment

from biz.djangoapps.ga_contract_operation.models import (
    ContractMail, ContractReminderMail,
    ContractTaskHistory, ContractTaskTarget, StudentRegisterTaskTarget,
    StudentUnregisterTaskTarget, AdditionalInfoUpdateTaskTarget, StudentMemberRegisterTaskTarget
)

from util.json_request import JsonResponseBadRequest


def _error_response(message):
    return JsonResponseBadRequest({
        'error': message,
    })

def get_additional_info_by_contract(contract):
    """
    :param contract:
    :return user_additional_settings: Additional settings value of user.
                                       key:user_id, value:dict{key:display_name, value:additional_settings_value}
             display_names: Display name list of additional settings on contract
             additional_searches: Additional settings list for w2ui
             additional_columns: Additional settings list for w2ui
    """
    additional_searches = []
    additional_columns = []

    additional_info_list = contract.additional_info.all()
    user_additional_settings = defaultdict(dict)
    display_names = []
    if bool(additional_info_list):
        for additional_info in additional_info_list:
            additional_searches.append({
                'field': additional_info.display_name,
                'caption': additional_info.display_name,
                'type': 'text',
            })
            additional_columns.append({
                'field': additional_info.display_name,
                'caption': additional_info.display_name,
                'sortable': True,
                'hidden': True,
                'size': 5,
            })
            display_names.append(additional_info.display_name)

        for setting in AdditionalInfoSetting.find_by_contract(contract):
            if setting.display_name in display_names:
                user_additional_settings[setting.user_id][setting.display_name] = setting.value

    return user_additional_settings, display_names, additional_searches, additional_columns


class PersonalinfoMaskExecutor(object):
    """
    Helper class for executing mask of personal information.
    """

    ERROR_CODE_ENROLLMENT_SPOC = 'spoc'
    ERROR_CODE_ENROLLMENT_MOOC = 'mooc'

    def __init__(self, contract):
        self.contract = contract
        _all_spoc_contract_details = ContractDetail.find_all_spoc()
        # all of spoc course ids
        self.spoc_course_ids = set([cd.course_id for cd in _all_spoc_contract_details])
        # spoc course ids which excluding courses relate with unavailable contract.
        self.enabled_spoc_course_ids = set([cd.course_id for cd in _all_spoc_contract_details if cd.contract.is_enabled()])
        # spoc course ids of target contract
        self.target_spoc_course_ids = set([cd.course_id for cd in contract.details.all()])
        # course ids of global course
        self.global_course_ids = set(CourseGlobalSetting.all_course_id())

    def check_enrollment(self, user):
        enrollment_course_ids = set([ce.course_id for ce in CourseEnrollment.enrollments_for_user(user)])
        # exclude global course
        enrollment_course_ids = enrollment_course_ids - self.global_course_ids

        enrollment_other_spoc_course_ids = (enrollment_course_ids & self.enabled_spoc_course_ids) - self.target_spoc_course_ids
        if enrollment_other_spoc_course_ids:
            return {'code': self.ERROR_CODE_ENROLLMENT_SPOC, 'course_id': enrollment_other_spoc_course_ids}

        enrollment_mooc_course_ids = enrollment_course_ids - self.spoc_course_ids
        if enrollment_mooc_course_ids:
            return {'code': self.ERROR_CODE_ENROLLMENT_MOOC, 'course_id': enrollment_mooc_course_ids}

        return None

    def disable_additional_info(self, contract_register):
        """
        Override masked value to additional information.

        Note: We can `NEVER` restore the masked value.
        """
        for additional_setting in AdditionalInfoSetting.find_by_user_and_contract(contract_register.user, self.contract):
            additional_setting.value = mask_utils.hash(additional_setting.value)
            additional_setting.save()

        # ContractRegister and ContractRegisterHistory for end-of-month
        contract_register.status = UNREGISTER_INVITATION_CODE
        contract_register.save()
        # CourseEnrollment only spoc
        if self.contract.is_spoc_available:
            for course_key in self.target_spoc_course_ids:
                if CourseEnrollment.is_enrolled(contract_register.user, course_key) and not has_staff_access(contract_register.user, course_key):
                    CourseEnrollment.unenroll(contract_register.user, course_key)


def create_reminder_task_input(request, history):
    mail_subject = request.POST.get('mail_subject', '')
    mail_body = request.POST.get('mail_body', '')
    contract = request.current_contract
    course = request.current_course
    task_input = {
        'contract_id': contract.id,
        'course_id': str(course.id),
        'history_id': history.id,
        'mail_subject': mail_subject,
        'mail_body': mail_body
    }
    return task_input
