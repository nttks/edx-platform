# -*- coding: utf-8 -*-
"""
Management command to generate a list of grade summary
for all biz students who registered any SPOC course.
"""
from collections import defaultdict, OrderedDict
import logging
from optparse import make_option
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test.client import RequestFactory
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.ga_achievement.achievement_store import ScoreStore
from biz.djangoapps.ga_achievement.models import ScoreBatchStatus
from biz.djangoapps.ga_contract.models import Contract, ContractAuth, AdditionalInfo
from biz.djangoapps.ga_invitation.models import ContractRegister, AdditionalInfoSetting
from biz.djangoapps.util.decorators import handle_command_exception, ExitWithWarning
from certificates.models import CertificateStatuses, GeneratedCertificate
from courseware import grades
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from student.models import UserStanding, CourseEnrollment
from xmodule.modulestore.django import modulestore
from xmodule.seq_module import SequenceDescriptor

log = logging.getLogger(__name__)


class CourseDoesNotExist(Exception):
    """
    This exception is raised in the case where None is returned from the modulestore
    """
    pass


class TargetSection(object):
    def __init__(self, section_descriptor):
        if not isinstance(section_descriptor, SequenceDescriptor) or section_descriptor.location.block_type != 'sequential':
            raise TypeError(u"section_descriptor must be a section object.")
        self.section_descriptor = section_descriptor
        self.chapter_descriptor = self.section_descriptor.get_parent()
        self.course_descriptor = self.chapter_descriptor.get_parent()

    @property
    def module_id(self):
        return unicode(self.section_descriptor.location)

    @property
    def column_name(self):
        """column_name MUST be unique in a course"""
        return u'{}{}{}'.format(
            self.chapter_descriptor.display_name,
            ScoreStore.FIELD_DELIMITER,
            self.section_descriptor.display_name,
        )


class GroupedTargetSections(OrderedDict, defaultdict):
    """
    A list of TargetSection object grouped by chapter

    e.g.)
    GroupedTargetSections([
        (BlockUsageLocator(CourseLocator(u'TestX', u'TS101', u'T1', None, None), u'chapter', u'Week1'), [TargetSection('Week1-1')]),
        (BlockUsageLocator(CourseLocator(u'TestX', u'TS101', u'T1', None, None), u'chapter', u'Week2'), [TargetSection('Week2-1'), TargetSection('Week2-2')]),
        :
    ])
    """
    def __init__(self, *args, **kwargs):
        super(GroupedTargetSections, self).__init__(*args, **kwargs)
        self.default_factory = list

    @property
    def course_key(self):
        # Note: We didn't check, but the course of all target_sections should be the same. So, get the first one
        if self.keys():
            return self.keys()[0].course_key
        return None

    @property
    def course_display_name(self):
        # Note: We didn't check, but the course of all target_sections should be the same. So, get the first one
        if self.keys():
            return self[self.keys()[0]][0].course_descriptor.display_name
        return None

    @property
    def target_sections(self):
        """
        Return a flattened list of TargetSection

        :return:
            e.g.)
            [TargetSection('Week1-1'), TargetSection('Week2-1'), TargetSection('Week2-2'), ..]
        """
        return sum(self.values(), [])

    def append(self, target_section):
        if not isinstance(target_section, TargetSection):
            raise TypeError(u"target_section must be a TargetSection object.")
        self[target_section.chapter_descriptor.location].append(target_section)


def get_grouped_target_sections(course):
    """Get target sections from course"""
    grouped_target_sections = GroupedTargetSections()
    for chapter in course.get_children():
        for section in chapter.get_children():
            # Note: Exclude sections if grading_type is not set. (#1996)
            if section.graded:
                has_score = False
                for vertical in section.get_children():
                    for component in vertical.get_children():
                        if component.has_score:
                            has_score = True
                            break
                if has_score:
                    grouped_target_sections.append(TargetSection(section))
    return grouped_target_sections


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
                raise ExitWithWarning(
                    "The specified contract does not exist or is not active. contract_id={}".format(contract_id)
                )
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

                    # Get target sections from course
                    grouped_target_sections = get_grouped_target_sections(course)

                    # Column
                    column = OrderedDict()
                    column[ScoreStore.FIELD_CONTRACT_ID] = contract.id
                    column[ScoreStore.FIELD_COURSE_ID] = unicode(course_key)
                    column[ScoreStore.FIELD_DOCUMENT_TYPE] = ScoreStore.FIELD_DOCUMENT_TYPE__COLUMN
                    if ContractAuth.objects.filter(contract_id=contract.id).exists():
                        column[_(ScoreStore.FIELD_LOGIN_CODE)] = ScoreStore.COLUMN_TYPE__TEXT
                    column[_(ScoreStore.FIELD_FULL_NAME)] = ScoreStore.COLUMN_TYPE__TEXT
                    column[_(ScoreStore.FIELD_USERNAME)] = ScoreStore.COLUMN_TYPE__TEXT
                    column[_(ScoreStore.FIELD_EMAIL)] = ScoreStore.COLUMN_TYPE__TEXT
                    additional_infos = AdditionalInfo.find_by_contract_id(contract.id)
                    for additional_info in additional_infos:
                        column[u'{}{}{}'.format(
                            _(ScoreStore.FIELD_ADDITIONAL_INFO),
                            ScoreStore.FIELD_DELIMITER,
                            additional_info.display_name)] = ScoreStore.COLUMN_TYPE__TEXT
                    column[_(ScoreStore.FIELD_STUDENT_STATUS)] = ScoreStore.COLUMN_TYPE__TEXT
                    column[_(ScoreStore.FIELD_CERTIFICATE_STATUS)] = ScoreStore.COLUMN_TYPE__TEXT
                    column[_(ScoreStore.FIELD_ENROLL_DATE)] = ScoreStore.COLUMN_TYPE__DATE
                    if course.self_paced:
                        column[_(ScoreStore.FIELD_EXPIRE_DATE)] = ScoreStore.COLUMN_TYPE__DATE
                    column[_(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)] = ScoreStore.COLUMN_TYPE__DATE
                    column[_(ScoreStore.FIELD_TOTAL_SCORE)] = ScoreStore.COLUMN_TYPE__PERCENT
                    for target_section in grouped_target_sections.target_sections:
                        column[target_section.column_name] = ScoreStore.COLUMN_TYPE__PERCENT
                        log.debug(u"column_name={}".format(target_section.column_name))

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
                        record[ScoreStore.FIELD_DOCUMENT_TYPE] = ScoreStore.FIELD_DOCUMENT_TYPE__RECORD
                        # Only in the case of a contract using login code, setting processing of data is performed.
                        if ContractAuth.objects.filter(contract_id=contract.id).exists():
                            record[_(ScoreStore.FIELD_LOGIN_CODE)] = contract_register.user.bizuser.login_code \
                                if hasattr(contract_register.user, 'bizuser') else None
                        record[_(ScoreStore.FIELD_FULL_NAME)] = user.profile.name \
                            if hasattr(user, 'profile') and user.profile else None
                        record[_(ScoreStore.FIELD_USERNAME)] = user.username
                        record[_(ScoreStore.FIELD_EMAIL)] = user.email
                        additional_infos = AdditionalInfo.find_by_contract_id(contract.id)
                        for additional_info in additional_infos:
                            record[u'{}{}{}'.format(
                                _(ScoreStore.FIELD_ADDITIONAL_INFO),
                                ScoreStore.FIELD_DELIMITER,
                                additional_info.display_name)] = AdditionalInfoSetting.get_value_by_display_name(
                                    user, contract.id, additional_info.display_name)
                        record[_(ScoreStore.FIELD_STUDENT_STATUS)] = student_status
                        record[_(ScoreStore.FIELD_CERTIFICATE_STATUS)] = certificate_status
                        record[_(ScoreStore.FIELD_ENROLL_DATE)] = course_enrollment.created if course_enrollment else None
                        # Add Expire Date only if course is self-paced
                        if course.self_paced:
                            record[_(ScoreStore.FIELD_EXPIRE_DATE)] = self_paced_api.get_course_end_date(course_enrollment)
                        record[_(ScoreStore.FIELD_CERTIFICATE_ISSUE_DATE)] = generated_certificate.created_date \
                            if generated_certificate else None
                        # Note: Set dummy value here to keep its order
                        record[_(ScoreStore.FIELD_TOTAL_SCORE)] = None
                        score_calculator = ScoreCalculator(course, user)
                        for target_section in grouped_target_sections.target_sections:
                            earned, possible, is_attempted = score_calculator.get_section_score(
                                target_section.module_id)
                            if possible == 0:
                                weighted_score = 0
                            else:
                                weighted_score = float(earned) / float(possible)
                            # Note: Set '―'(U+2015) if user has not submitted any problem in the section (#1816)
                            # Note: In case where any problem.whole_point_addition is set to enabled,
                            #       is_attempted can be False, so 'earned > 0' is needed. (#1917)
                            record[target_section.column_name] = weighted_score \
                                if is_attempted or earned > 0 else ScoreStore.VALUE__NOT_ATTEMPTED
                        record[_(ScoreStore.FIELD_TOTAL_SCORE)] = score_calculator.get_total_score()
                        records.append(record)

                    score_store = ScoreStore(contract.id, unicode(course_key))
                    score_store.remove_documents()
                    if records:
                        score_store.set_documents([column])
                        score_store.set_documents(records)
                        score_store.drop_indexes()
                        score_store.ensure_indexes()

                except CourseDoesNotExist:
                    log.warning(u"This course does not exist in modulestore. course_id={}".format(unicode(course_key)))
                    ScoreBatchStatus.save_for_error(contract.id, course_key)
                except Exception as ex:
                    error_flag = True
                    log.error(u"Unexpected error occurred: {}".format(ex))
                    ScoreBatchStatus.save_for_error(contract.id, course_key)
                else:
                    ScoreBatchStatus.save_for_finished(contract.id, course_key, len(records))

        if error_flag:
            raise CommandError("Error occurred while handling update_biz_score_status command.")


class ScoreCalculator(object):
    def __init__(self, course, user):
        request = RequestFactory().get('/')
        try:
            start = time.clock()
            self.grade_summary = grades.grade(user, request, course)
            end = time.clock()
            log.debug(u"Processed time for grades.grade ... {:.2f}s".format(end - start))
        except Exception as e:
            log.warning(u"Cannot get grade_summary. {}".format(e))
            self.grade_summary = {}

    def get_section_score(self, module_id):
        earned = 0
        possible = 0
        is_attempted = False
        totaled_scores = self.grade_summary.get('totaled_scores', {})
        for section_format, scores in totaled_scores.iteritems():
            for score in scores:
                if score.module_id == module_id:
                    earned = score.earned
                    possible = score.possible
                    is_attempted = score.is_attempted
                    break
        return earned, possible, is_attempted

    def get_total_score(self):
        return self.grade_summary.get('percent', 0.0)
