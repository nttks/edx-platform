"""
Management command to generate a list of playback summary
for all biz students who registered any SPOC course.
"""
from collections import OrderedDict
import logging
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus
from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore
from biz.djangoapps.ga_achievement.log_store import PlaybackLogStore
from biz.djangoapps.ga_contract.models import ContractDetail, AdditionalInfo
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting
from biz.djangoapps.util.decorators import handle_command_exception
from biz.djangoapps.util.hash_utils import to_target_id
from student.models import UserStanding, CourseEnrollment
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)


class CourseDoesNotExist(Exception):
    """
    This exception is raised in the case where None is returned from the modulestore
    """
    pass


class TargetVertical(object):
    def __init__(self, section_descriptor, vertical_descriptor):
        self.section_descriptor = section_descriptor
        self.vertical_descriptor = vertical_descriptor

    @property
    def vertical_id(self):
        return self.vertical_descriptor.location.block_id

    @property
    def section_name(self):
        return self.section_descriptor.display_name

    @property
    def column_name(self):
        return u'{}{}{}'.format(
            self.section_descriptor.display_name,
            PlaybackStore.FIELD_DELIMITER,
            self.vertical_descriptor.display_name,
        )


class Command(BaseCommand):
    """
    Generate a list of playback summary for all biz students who registered any SPOC course.
    """
    help = """
    Usage: python manage.py lms --settings=aws update_biz_playback_status [--debug] [<contract_id>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
    )

    @handle_command_exception(settings.BIZ_SET_PLAYBACK_COMMAND_OUTPUT)
    def handle(self, *args, **options):
        # Note: BaseCommand translations are deactivated by default, so activate here
        translation.activate(settings.LANGUAGE_CODE)

        debug = options.get('debug')
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
                log.debug(u"Command update_biz_playback_status is now processing [{}][{}]".format(
                    contract_id, unicode(course_key)))
                PlaybackBatchStatus.save_for_started(contract_id, course_key)

                # Get SPOC video components from course
                course = modulestore().get_course(course_key, depth=4)
                if not course:
                    raise CourseDoesNotExist()
                target_vertical_sections = []
                for section in course.get_children():
                    target_verticals = []
                    for subsection in section.get_children():
                        for vertical in subsection.get_children():
                            has_spoc_video = False
                            for component in vertical.get_children():
                                if component.location.block_type == 'jwplayerxblock':
                                    has_spoc_video = True
                                    break
                            if has_spoc_video:
                                target_verticals.append(TargetVertical(section, vertical))
                    if len(target_verticals) > 0:
                        target_vertical_sections.append(target_verticals)
                log.debug(u"course_id={}, target_vertical_sections={}".format(
                    unicode(course_key), [[v.vertical_id for v in s] for s in target_vertical_sections]))

                # Column
                column = OrderedDict()
                column[PlaybackStore.FIELD_CONTRACT_ID] = contract_id
                column[PlaybackStore.FIELD_COURSE_ID] = unicode(course_key)
                column[PlaybackStore.FIELD_DOCUMENT_TYPE] = PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN
                column[_(PlaybackStore.FIELD_FULL_NAME)] = PlaybackStore.COLUMN_TYPE__TEXT
                column[_(PlaybackStore.FIELD_USERNAME)] = PlaybackStore.COLUMN_TYPE__TEXT
                column[_(PlaybackStore.FIELD_EMAIL)] = PlaybackStore.COLUMN_TYPE__TEXT
                additional_infos = AdditionalInfo.find_by_contract_id(contract_id)
                for additional_info in additional_infos:
                    column[u'{}{}{}'.format(
                        _(PlaybackStore.FIELD_ADDITIONAL_INFO),
                        PlaybackStore.FIELD_DELIMITER,
                        additional_info.display_name)] = PlaybackStore.COLUMN_TYPE__TEXT
                column[_(PlaybackStore.FIELD_STUDENT_STATUS)] = PlaybackStore.COLUMN_TYPE__TEXT
                if target_vertical_sections:
                    column[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] = PlaybackStore.COLUMN_TYPE__TIME
                for target_verticals in target_vertical_sections:
                    for target_vertical in target_verticals:
                        column[target_vertical.column_name] = PlaybackStore.COLUMN_TYPE__TIME
                    column[u'{}{}{}'.format(
                        target_vertical.section_name,
                        PlaybackStore.FIELD_DELIMITER,
                        _(PlaybackStore.FIELD_SECTION_PLAYBACK_TIME))] = PlaybackStore.COLUMN_TYPE__TIME

                # Records
                records = []
                for contract_register in ContractRegister.find_input_and_register_by_contract(
                        contract_id).select_related('user__standing', 'user__profile'):
                    user = contract_register.user
                    # Student Status
                    course_enrollment = CourseEnrollment.get_enrollment(user, course_key)
                    if hasattr(user, 'standing') and user.standing \
                        and user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                        student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__DISABLED)
                    elif not course_enrollment:
                        student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__NOT_ENROLLED)
                    elif course_enrollment.is_active:
                        student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED)
                    else:
                        student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED)

                    # Records
                    record = OrderedDict()
                    record[PlaybackStore.FIELD_CONTRACT_ID] = contract_id
                    record[PlaybackStore.FIELD_COURSE_ID] = unicode(course_key)
                    record[PlaybackStore.FIELD_DOCUMENT_TYPE] = PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD
                    record[_(PlaybackStore.FIELD_FULL_NAME)] = user.profile.name \
                        if hasattr(user, 'profile') and user.profile else None
                    record[_(PlaybackStore.FIELD_USERNAME)] = user.username
                    record[_(PlaybackStore.FIELD_EMAIL)] = user.email
                    for additional_info in additional_infos:
                        record[u'{}{}{}'.format(
                            _(PlaybackStore.FIELD_ADDITIONAL_INFO),
                            PlaybackStore.FIELD_DELIMITER,
                            additional_info.display_name)] = AdditionalInfoSetting.get_value_by_display_name(
                                user, contract_id, additional_info.display_name)
                    record[_(PlaybackStore.FIELD_STUDENT_STATUS)] = student_status
                    if target_vertical_sections:
                        # Note: Set dummy value here to keep its order
                        record[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] = None

                        # Get duration summary from playback log store
                        playback_log_store = PlaybackLogStore(unicode(course_key), to_target_id(user.id))
                        duration_summary = playback_log_store.aggregate_duration_by_vertical()

                        total_playback_time = 0
                        for target_verticals in target_vertical_sections:
                            section_playback_time = 0
                            for target_vertical in target_verticals:
                                duration = duration_summary.get(target_vertical.vertical_id, 0)
                                section_playback_time = section_playback_time + duration
                                total_playback_time = total_playback_time + duration
                                log.debug(u"course_id={}, vertical={}, column_name={}, target_id={}, duration={}".format(
                                    unicode(course_key), target_vertical.vertical_id, target_vertical.column_name,
                                    to_target_id(user.id), duration))
                                # Playback Time for each vertical
                                record[target_vertical.column_name] = duration
                            # Playback Time for each section
                            record[u'{}{}{}'.format(
                                target_vertical.section_name,
                                PlaybackStore.FIELD_DELIMITER,
                                _(PlaybackStore.FIELD_SECTION_PLAYBACK_TIME))] = section_playback_time

                        # Total Playback Time
                        record[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] = total_playback_time
                    records.append(record)

                playback_store = PlaybackStore(contract_id, unicode(course_key))
                playback_store.remove_documents()
                if records:
                    playback_store.set_documents([column])
                    playback_store.set_documents(records)
                    playback_store.drop_indexes()
                    playback_store.ensure_indexes()
                PlaybackBatchStatus.save_for_finished(contract_id, course_key, len(records))

            except CourseDoesNotExist:
                log.warning(u"This course does not exist in modulestore. course_id={}".format(unicode(course_key)))
                PlaybackBatchStatus.save_for_error(contract_id, course_key)
            except Exception as ex:
                error_flag = True
                log.error(u"Unexpected error occurred: {}".format(ex))
                PlaybackBatchStatus.save_for_error(contract_id, course_key)

        if error_flag:
            raise CommandError("Error occurred while handling update_biz_playback_status command.")
