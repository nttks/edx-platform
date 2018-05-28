"""
Management command to generate a list of playback summary
for all biz students who registered any SPOC course.
"""
import logging
import time
from collections import defaultdict, OrderedDict
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore
from biz.djangoapps.ga_achievement.log_store import PlaybackLogStore
from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus
from biz.djangoapps.ga_contract.models import Contract, AdditionalInfo, ContractAuth
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting
from biz.djangoapps.util.decorators import handle_command_exception, ExitWithWarning
from biz.djangoapps.util.hash_utils import to_target_id
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from student.models import UserStanding, CourseEnrollment
from xmodule.modulestore.django import modulestore
from xmodule.vertical_block import VerticalBlock

log = logging.getLogger(__name__)


class CourseDoesNotExist(Exception):
    """
    This exception is raised in the case where None is returned from the modulestore
    """
    pass


class TargetVertical(object):
    def __init__(self, vertical_descriptor):
        if not isinstance(vertical_descriptor, VerticalBlock):
            raise TypeError(u"vertical_descriptor must be a vertical object.")
        self.vertical_descriptor = vertical_descriptor
        self.section_descriptor = self.vertical_descriptor.get_parent()
        self.chapter_descriptor = self.section_descriptor.get_parent()

    @property
    def chapter_name(self):
        return self.chapter_descriptor.display_name

    @property
    def vertical_id(self):
        return self.vertical_descriptor.location.block_id

    @property
    def column_name(self):
        """column_name MUST be unique in a course"""
        return u'{}{}{}'.format(
            self.chapter_descriptor.display_name,
            PlaybackStore.FIELD_DELIMITER,
            self.vertical_descriptor.display_name,
        )


class GroupedTargetVerticals(OrderedDict, defaultdict):
    """
    A list of TargetVertical object grouped by chapter

    e.g.)
    GroupedTargetVerticals([
        (BlockUsageLocator(CourseLocator(u'TestX', u'TS101', u'T1', None, None), u'chapter', u'Week1'), [TargetVertical('Week1-1-1')]),
        (BlockUsageLocator(CourseLocator(u'TestX', u'TS101', u'T1', None, None), u'chapter', u'Week2'), [TargetVertical('Week2-1-1'), TargetVertical('Week2-2-1'), TargetVertical('Week2-2-2')]),
        :
    ])
    """
    def __init__(self, *args, **kwargs):
        super(GroupedTargetVerticals, self).__init__(*args, **kwargs)
        self.default_factory = list

    def append(self, target_vertical):
        if not isinstance(target_vertical, TargetVertical):
            raise TypeError(u"target_vertical must be a TargetVertical object.")
        self[target_vertical.chapter_descriptor.location].append(target_vertical)


def get_grouped_target_verticals(course):
    """Get verticals with SPOC video component from course"""
    grouped_target_verticals = GroupedTargetVerticals()
    for chapter in course.get_children():
        for section in chapter.get_children():
            for vertical in section.get_children():
                for component in vertical.get_children():
                    if component.location.block_type == 'jwplayerxblock':
                        grouped_target_verticals.append(TargetVertical(vertical))
                        break
    return grouped_target_verticals


class Command(BaseCommand):
    """
    Generate a list of playback summary for all biz students who registered any SPOC course.
    """
    help = """
    Usage: python manage.py lms --settings=aws update_biz_playback_status [--debug] [--force] [--excludes=<exclude_ids>]|[<contract_id>]
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

    @handle_command_exception(settings.BIZ_SET_PLAYBACK_COMMAND_OUTPUT)
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
                contracts = [Contract.objects.enabled(days_after=-1).get(pk=contract_id)]
            except Contract.DoesNotExist:
                raise ExitWithWarning(
                    "The specified contract does not exist or is not active. contract_id={}".format(contract_id)
                )
        else:
            contracts = Contract.objects.enabled(days_after=-1).all().exclude(id__in=exclude_ids).order_by('id')
        log.debug(u"contract_ids=[{}]".format(','.join([str(contract.id) for contract in contracts])))

        error_flag = False
        for contract in contracts:
            # Check if batch process for the contract has not yet started today
            if PlaybackBatchStatus.exists_today(contract.id):
                if force:
                    log.warning(
                        u"Command update_biz_playback_status for contract({}) has already started today, but force to start.".format(
                            contract.id))
                else:
                    log.warning(
                        u"Command update_biz_playback_status for contract({}) has already started today, so skip.".format(
                            contract.id))
                    continue

            # Save the existence of ContractAuth object
            use_contract_auth = ContractAuth.objects.filter(contract=contract).exists()

            q_contract_register = ContractRegister.find_input_and_register_by_contract(contract.id)
            count_contract_register = q_contract_register.count()
            for contract_detail in contract.details.all():
                try:
                    course_key = contract_detail.course_id
                    unicode_course_key = unicode(course_key)
                    log.info(
                        u"Command update_biz_playback_status for contract({}) and course({}) is now processing...".format(
                            contract.id, unicode_course_key))
                    PlaybackBatchStatus.save_for_started(contract.id, course_key)

                    # Check if course exists in modulestore
                    course = modulestore().get_course(course_key, depth=4)
                    if not course:
                        raise CourseDoesNotExist()

                    # Get duration summary from playback log store
                    duration_summary = PlaybackLogStore(unicode_course_key).aggregate_duration_by_vertical_and_target()

                    # Get target verticals from course
                    grouped_target_verticals = get_grouped_target_verticals(course)

                    # Column
                    column = OrderedDict()
                    column[PlaybackStore.FIELD_CONTRACT_ID] = contract.id
                    column[PlaybackStore.FIELD_COURSE_ID] = unicode_course_key
                    column[PlaybackStore.FIELD_DOCUMENT_TYPE] = PlaybackStore.FIELD_DOCUMENT_TYPE__COLUMN
                    # Only in the case of a contract using login code, setting processing of column is performed.
                    if use_contract_auth:
                        column[_(PlaybackStore.FIELD_LOGIN_CODE)] = PlaybackStore.COLUMN_TYPE__TEXT
                    column[_(PlaybackStore.FIELD_FULL_NAME)] = PlaybackStore.COLUMN_TYPE__TEXT
                    column[_(PlaybackStore.FIELD_USERNAME)] = PlaybackStore.COLUMN_TYPE__TEXT
                    column[_(PlaybackStore.FIELD_EMAIL)] = PlaybackStore.COLUMN_TYPE__TEXT
                    additional_infos = AdditionalInfo.find_by_contract_id(contract.id)
                    for additional_info in additional_infos:
                        column[u'{}{}{}'.format(
                            _(PlaybackStore.FIELD_ADDITIONAL_INFO),
                            PlaybackStore.FIELD_DELIMITER,
                            additional_info.display_name)] = PlaybackStore.COLUMN_TYPE__TEXT
                    column[_(PlaybackStore.FIELD_STUDENT_STATUS)] = PlaybackStore.COLUMN_TYPE__TEXT
                    if grouped_target_verticals.keys():
                        column[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] = PlaybackStore.COLUMN_TYPE__TIME
                    for target_verticals in grouped_target_verticals.values():
                        for target_vertical in target_verticals:
                            column[target_vertical.column_name] = PlaybackStore.COLUMN_TYPE__TIME
                            log.debug(u"column_name={}".format(target_vertical.column_name))
                        column[u'{}{}{}'.format(
                            target_vertical.chapter_name,
                            PlaybackStore.FIELD_DELIMITER,
                            _(PlaybackStore.FIELD_SECTION_PLAYBACK_TIME))] = PlaybackStore.COLUMN_TYPE__TIME

                    # Records
                    records = []
                    for contract_register in q_contract_register.select_related('user__standing', 'user__profile'):
                        user = contract_register.user
                        # Student Status
                        course_enrollment = CourseEnrollment.get_enrollment(user, course_key)
                        if hasattr(user, 'standing') and user.standing \
                            and user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                            student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__DISABLED)
                        elif not course_enrollment:
                            student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__NOT_ENROLLED)
                        elif self_paced_api.is_course_closed(course_enrollment):
                            student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__EXPIRED)
                        elif course_enrollment.is_active:
                            student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__ENROLLED)
                        else:
                            student_status = _(PlaybackStore.FIELD_STUDENT_STATUS__UNENROLLED)

                        # Records
                        record = OrderedDict()
                        record[PlaybackStore.FIELD_CONTRACT_ID] = contract.id
                        record[PlaybackStore.FIELD_COURSE_ID] = unicode_course_key
                        record[PlaybackStore.FIELD_DOCUMENT_TYPE] = PlaybackStore.FIELD_DOCUMENT_TYPE__RECORD
                        # Only in the case of a contract using login code, setting processing of data is performed.
                        if use_contract_auth:
                            record[_(PlaybackStore.FIELD_LOGIN_CODE)] = contract_register.user.bizuser.login_code \
                                if hasattr(contract_register.user, 'bizuser') else None
                        record[_(PlaybackStore.FIELD_FULL_NAME)] = user.profile.name \
                            if hasattr(user, 'profile') and user.profile else None
                        record[_(PlaybackStore.FIELD_USERNAME)] = user.username
                        record[_(PlaybackStore.FIELD_EMAIL)] = user.email
                        for additional_info in additional_infos:
                            record[u'{}{}{}'.format(
                                _(PlaybackStore.FIELD_ADDITIONAL_INFO),
                                PlaybackStore.FIELD_DELIMITER,
                                additional_info.display_name)] = AdditionalInfoSetting.get_value_by_display_name(
                                    user, contract.id, additional_info.display_name)
                        record[_(PlaybackStore.FIELD_STUDENT_STATUS)] = student_status
                        if grouped_target_verticals.keys():
                            # Note: Set dummy value here to keep its order
                            record[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] = None

                            target_id = to_target_id(user.id)

                            total_playback_time = 0
                            for target_verticals in grouped_target_verticals.values():
                                section_playback_time = 0
                                for target_vertical in target_verticals:
                                    duration = duration_summary.get(PlaybackStore.FIELD_DELIMITER.join([target_vertical.vertical_id, target_id]), 0)
                                    section_playback_time = section_playback_time + duration
                                    total_playback_time = total_playback_time + duration
                                    # Playback Time for each vertical
                                    record[target_vertical.column_name] = duration
                                # Playback Time for each section
                                record[u'{}{}{}'.format(
                                    target_vertical.chapter_name,
                                    PlaybackStore.FIELD_DELIMITER,
                                    _(PlaybackStore.FIELD_SECTION_PLAYBACK_TIME))] = section_playback_time

                            # Total Playback Time
                            record[_(PlaybackStore.FIELD_TOTAL_PLAYBACK_TIME)] = total_playback_time
                        records.append(record)

                    playback_store = PlaybackStore(contract.id, unicode_course_key)

                    for i in range(settings.MAX_RETRY_SET_DOCUMENTS + 1):
                        for j in range(settings.MAX_RETRY_REMOVE_DOCUMENTS + 1):
                            playback_store.remove_documents()

                            # Confirm remove_documents.
                            count_playback_store = playback_store.get_count()
                            if count_playback_store == 0:
                                log.info(u"Removed PlaybackStore records. contract_id={} course_id={}".format(
                                    contract.id, unicode_course_key))
                                break;

                            if j >= settings.MAX_RETRY_REMOVE_DOCUMENTS:
                                raise Exception(u"Can not remove PlaybackStore record count({}). contract_id={} course_id={}".format(
                                    count_playback_store, contract.id, unicode_course_key))

                            log.warning(u"Can not remove(try:{},sleep:{}) PlaybackStore record count({}). contract_id={} course_id={}".format(
                                j + 1, settings.SLEEP_RETRY_REMOVE_DOCUMENTS, count_playback_store, contract.id, unicode_course_key))
                            if settings.SLEEP_RETRY_REMOVE_DOCUMENTS:
                                time.sleep(settings.SLEEP_RETRY_REMOVE_DOCUMENTS)

                        len_records = len(records)
                        if len_records == 0:
                            break;

                        playback_store.set_documents([column])
                        playback_store.set_documents(records)
                        playback_store.drop_indexes()
                        playback_store.ensure_indexes()

                        # Confirm set_documents. (compare with record count without column)
                        count_playback_store = playback_store.get_count() - 1
                        if count_playback_store == count_contract_register == len_records:
                            log.info(u"Stored PlaybackStore record count({}). contract_id={} course_id={}".format(
                                count_playback_store, contract.id, unicode_course_key))
                            break;

                        if i >= settings.MAX_RETRY_SET_DOCUMENTS:
                            raise Exception(u"PlaybackStore record count({}) does not match Contract Register record count({}) or records count({}). contract_id={} course_id={}".format(
                                count_playback_store, count_contract_register, len_records, contract.id, unicode_course_key))

                        log.warning(u"Can not store(try:{},sleep:{}) PlaybackStore record count({}) does not match Contract Register record count({}) or records count({}). contract_id={} course_id={}".format(
                            i + 1, settings.SLEEP_RETRY_SET_DOCUMENTS, count_playback_store, count_contract_register, len_records, contract.id, unicode_course_key))
                        if settings.SLEEP_RETRY_SET_DOCUMENTS:
                            time.sleep(settings.SLEEP_RETRY_SET_DOCUMENTS)

                except CourseDoesNotExist:
                    log.warning(u"This course does not exist in modulestore. course_id={}".format(unicode_course_key))
                    PlaybackBatchStatus.save_for_error(contract.id, course_key)
                except Exception as ex:
                    error_flag = True
                    log.error(u"Unexpected error occurred: {}".format(ex))
                    PlaybackBatchStatus.save_for_error(contract.id, course_key)
                else:
                    PlaybackBatchStatus.save_for_finished(contract.id, course_key, len(records))

        if error_flag:
            raise CommandError("Error occurred while handling update_biz_playback_status command.")
