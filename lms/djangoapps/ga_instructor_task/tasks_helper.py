# -*- coding: utf-8 -*-
"""
This file contains tasks that are designed to perform background operations on the
running state of a course.
cf. instructor_task/tasks_helper.py
"""
from datetime import datetime
import logging
from pytz import UTC
from time import time

from courseware.access import has_access
from django.utils.translation import ugettext as _
from .ga_instructor_report_record import GaScoreDetailReportRecord, GaPlaybackStatusReportRecord
from instructor_analytics.csvs import format_dictlist
from instructor_task.tasks_helper import TaskProgress, upload_csv_to_report_store
from student.models import CourseEnrollment, CourseAccessRole, UserStanding
from xmodule.modulestore.django import modulestore

# define different loggers for use within tasks and on client side
TASK_LOG = logging.getLogger('edx.celery.task')


def generate_score_detail_report_helper(_xmodule_instance_args, _entry_id, course_key, _task_input, action_name):
    start_time = time()
    start_date = datetime.now(UTC)
    num_reports = 1
    task_progress = TaskProgress(action_name, num_reports, start_time)

    fmt = u'Task: {task_id}, InstructorTask ID: {entry_id}, Course: {course_id}, Input: {task_input}'
    task_info_string = fmt.format(
        task_id=_xmodule_instance_args.get('task_id') if _xmodule_instance_args is not None else None,
        entry_id=_entry_id,
        course_id=course_key,
        task_input=_task_input
    )
    TASK_LOG.info(u'{}, Task type: {}, Starting task execution'.format(task_info_string, action_name))

    current_step = {'step': 'Gathering students score in course'}
    task_progress.update_task_state(extra_meta=current_step)

    records = []
    try:
        from biz.djangoapps.ga_achievement.achievement_store import AchievementStoreBase
        from biz.djangoapps.ga_achievement.management.commands.update_biz_score_status import (
            CourseDoesNotExist,
            get_grouped_target_sections,
            ScoreCalculator,
        )

        # Check if course exists in modulestore
        course = modulestore().get_course(course_key)
        if not course:
            raise CourseDoesNotExist()

        # Get target sections from course
        grouped_target_sections = get_grouped_target_sections(course)

        # Column
        header = [
            _(GaScoreDetailReportRecord.FIELD_USERNAME),
            _(GaScoreDetailReportRecord.FIELD_EMAIL),
            _(GaScoreDetailReportRecord.FIELD_GLOBAL_STAFF),
            _(GaScoreDetailReportRecord.FIELD_COURSE_ADMIN),
            _(GaScoreDetailReportRecord.FIELD_COURSE_STAFF),
            _(GaScoreDetailReportRecord.FIELD_ENROLL_STATUS),
            _(GaScoreDetailReportRecord.FIELD_ENROLL_DATE),
            _(GaScoreDetailReportRecord.FIELD_RESIGN_STATUS),
            _(GaScoreDetailReportRecord.FIELD_RESIGN_DATE),
            _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE),
        ]
        for target_sections in grouped_target_sections.values():
            chapter_name = None
            for target_section in target_sections:
                header.append(target_section.column_name)
                chapter_name = target_section.chapter_descriptor.display_name
            header.append(u'{}{}{}'.format(
                chapter_name,
                AchievementStoreBase.FIELD_DELIMITER,
                _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE))
            )

        # Records
        students_in_course = CourseEnrollment.objects.enrolled_and_dropped_out_users(
                                course_key).select_related('standing', 'profile')
        total_students = students_in_course.count()
        student_counter = 0
        for user in students_in_course:
            student_counter += 1
            TASK_LOG.info(u'{}, Task type: {}, student:{}, Score calculation in-progress for students: {}/{}'.format(
                          task_info_string, action_name, user.id, student_counter, total_students))

            # Student Status
            course_enrollment = CourseEnrollment.get_enrollment(user, course_key)

            student_status = UserStanding.ACCOUNT_ENABLED
            student_resign_date = ''
            if hasattr(user, 'standing') and user.standing:
                student_status = user.standing.account_status
                if user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                    student_resign_date = user.standing.standing_last_changed_at

            is_course_instructor = bool(has_access(user, 'instructor', course))
            is_course_staff = bool(has_access(user, 'staff', course))

            # Record
            record = GaScoreDetailReportRecord()
            record[_(GaScoreDetailReportRecord.FIELD_COURSE_ID)] = unicode(course_key)
            record[_(GaScoreDetailReportRecord.FIELD_USERNAME)] = user.username
            record[_(GaScoreDetailReportRecord.FIELD_EMAIL)] = user.email
            record[_(GaScoreDetailReportRecord.FIELD_GLOBAL_STAFF)] = int(user.is_staff)
            record[_(GaScoreDetailReportRecord.FIELD_COURSE_ADMIN)] = int(is_course_instructor)
            record[_(GaScoreDetailReportRecord.FIELD_COURSE_STAFF)] = int(is_course_staff)

            record[_(GaScoreDetailReportRecord.FIELD_ENROLL_STATUS)] = \
                1 if course_enrollment and course_enrollment.is_active else 0
            record[_(GaScoreDetailReportRecord.FIELD_ENROLL_DATE)] = \
                course_enrollment.created if course_enrollment else ''
            record[_(GaScoreDetailReportRecord.FIELD_RESIGN_STATUS)] = \
                1 if student_status == UserStanding.ACCOUNT_DISABLED else 0
            record[_(GaScoreDetailReportRecord.FIELD_RESIGN_DATE)] = \
                student_resign_date if student_resign_date else ''

            score_calculator = ScoreCalculator(course, user)
            record[_(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE)] = \
                '{:.01%}'.format(score_calculator.get_total_score())

            for target_section in grouped_target_sections.target_sections:
                chapter_name = target_section.chapter_descriptor.display_name
                chapter_score_column = u'{}{}{}'.format(
                    chapter_name,
                    AchievementStoreBase.FIELD_DELIMITER,
                    _(GaScoreDetailReportRecord.FIELD_TOTAL_SCORE))
                if chapter_score_column not in record:
                    record[chapter_score_column] = 0.0

                earned, possible, is_attempted = score_calculator.get_section_score(
                        target_section.module_id)
                if possible == 0:
                    weighted_score = 0
                else:
                    weighted_score = float(earned) / float(possible)
                # Note: In case where any problem.whole_point_addition is set to enabled,
                #       is_attempted can be False, so 'earned > 0' is needed. (#1917)
                record[target_section.column_name] = '{:.01%}'.format(weighted_score) \
                    if is_attempted or earned > 0 else ''

                if is_attempted or earned > 0:
                    # chapter score
                    record[chapter_score_column] += float(earned)

            records.append(record)
            task_progress.succeeded += 1
    except CourseDoesNotExist:
        TASK_LOG.warning(u"This course does not exist in modulestore. course_id={}".format(unicode(course_key)))
        task_progress.failed += 1
        return task_progress.update_task_state(extra_meta={'step': 'Not exist course'})
    except Exception as ex:
        TASK_LOG.error(u"Unexpected error occurred: {}".format(ex))
        task_progress.failed += 1
        return task_progress.update_task_state(extra_meta={'step': 'Error'})

    TASK_LOG.info(u'{}, Task type: {}, Score calculation completed for students: {}/{}'.format(
        task_info_string,
        action_name,
        student_counter,
        total_students))

    __, rows = format_dictlist(records, header)
    rows.insert(0, header)

    current_step = {'step': 'Uploading CSV'}
    task_progress.update_task_state(extra_meta=current_step)

    upload_csv_to_report_store(rows, 'score_detail_report', course_key, start_date)
    return task_progress.update_task_state(extra_meta=current_step)


def generate_playback_status_report_helper(_xmodule_instance_args, _entry_id, course_key, _task_input, action_name):
    start_time = time()
    start_date = datetime.now(UTC)
    num_reports = 1
    task_progress = TaskProgress(action_name, num_reports, start_time)

    fmt = u'Task: {task_id}, InstructorTask ID: {entry_id}, Course: {course_id}, Input: {task_input}'
    task_info_string = fmt.format(
        task_id=_xmodule_instance_args.get('task_id') if _xmodule_instance_args is not None else None,
        entry_id=_entry_id,
        course_id=course_key,
        task_input=_task_input
    )
    TASK_LOG.info(u'{}, Task type: {}, Starting task execution'.format(task_info_string, action_name))

    current_step = {'step': 'Gathering playback status in course'}
    task_progress.update_task_state(extra_meta=current_step)

    records = []
    try:
        from biz.djangoapps.ga_achievement.achievement_store import AchievementStoreBase
        from biz.djangoapps.ga_achievement.log_store import PlaybackLogStore
        from biz.djangoapps.ga_achievement.management.commands.update_biz_playback_status import (
            CourseDoesNotExist,
            get_grouped_target_verticals,
        )
        from biz.djangoapps.util import datetime_utils, hash_utils

        # Check if course exists in modulestore
        course = modulestore().get_course(course_key)
        if not course:
            raise CourseDoesNotExist()

        # Get target verticals from course
        grouped_target_verticals = get_grouped_target_verticals(course)

        # Column
        header = [
            _(GaPlaybackStatusReportRecord.FIELD_USERNAME),
            _(GaPlaybackStatusReportRecord.FIELD_EMAIL),
            _(GaPlaybackStatusReportRecord.FIELD_GLOBAL_STAFF),
            _(GaPlaybackStatusReportRecord.FIELD_COURSE_ADMIN),
            _(GaPlaybackStatusReportRecord.FIELD_COURSE_STAFF),
            _(GaPlaybackStatusReportRecord.FIELD_ENROLL_STATUS),
            _(GaPlaybackStatusReportRecord.FIELD_ENROLL_DATE),
            _(GaPlaybackStatusReportRecord.FIELD_RESIGN_STATUS),
            _(GaPlaybackStatusReportRecord.FIELD_RESIGN_DATE),
            _(GaPlaybackStatusReportRecord.FIELD_TOTAL_PLAYBACK_TIME),
        ]
        for target_verticals in grouped_target_verticals.values():
            chapter_name = None
            for target_vertical in target_verticals:
                header.append(target_vertical.column_name)
                chapter_name = target_vertical.chapter_name
            header.append(u'{}{}{}'.format(
                chapter_name,
                AchievementStoreBase.FIELD_DELIMITER,
                _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
            )

        # Records
        students_in_course = CourseEnrollment.objects.enrolled_and_dropped_out_users(
                                course_key).select_related('standing', 'profile')
        total_students = students_in_course.count()
        student_counter = 0
        for user in students_in_course:
            student_counter += 1
            TASK_LOG.info(u'{}, Task type: {}, student:{}, Playback calculation in-progress for students: {}/{}'.format(
                          task_info_string, action_name, user.id, student_counter, total_students))

            # Student Status
            course_enrollment = CourseEnrollment.get_enrollment(user, course_key)

            student_status = UserStanding.ACCOUNT_ENABLED
            student_resign_date = ''
            if hasattr(user, 'standing') and user.standing:
                student_status = user.standing.account_status
                if user.standing.account_status == UserStanding.ACCOUNT_DISABLED:
                    student_resign_date = user.standing.standing_last_changed_at

            is_course_instructor = bool(has_access(user, 'instructor', course))
            is_course_staff = bool(has_access(user, 'staff', course))

            # Record
            record = GaPlaybackStatusReportRecord()
            record[_(GaPlaybackStatusReportRecord.FIELD_COURSE_ID)] = unicode(course_key)
            record[_(GaPlaybackStatusReportRecord.FIELD_USERNAME)] = user.username
            record[_(GaPlaybackStatusReportRecord.FIELD_EMAIL)] = user.email
            record[_(GaPlaybackStatusReportRecord.FIELD_GLOBAL_STAFF)] = int(user.is_staff)
            record[_(GaPlaybackStatusReportRecord.FIELD_COURSE_ADMIN)] = int(is_course_instructor)
            record[_(GaPlaybackStatusReportRecord.FIELD_COURSE_STAFF)] = int(is_course_staff)

            record[_(GaPlaybackStatusReportRecord.FIELD_ENROLL_STATUS)] = \
                1 if course_enrollment and course_enrollment.is_active else 0
            record[_(GaPlaybackStatusReportRecord.FIELD_ENROLL_DATE)] = \
                course_enrollment.created if course_enrollment else ''
            record[_(GaPlaybackStatusReportRecord.FIELD_RESIGN_STATUS)] = \
                1 if student_status == UserStanding.ACCOUNT_DISABLED else 0
            record[_(GaPlaybackStatusReportRecord.FIELD_RESIGN_DATE)] = \
                student_resign_date if student_resign_date else ''

            # Get duration summary from playback log store
            playback_log_store = PlaybackLogStore(unicode(course_key), hash_utils.to_target_id(user.id))
            duration_summary = playback_log_store.aggregate_duration_by_vertical()

            total_playback_time = 0
            for target_verticals in grouped_target_verticals.values():
                chapter_name = None
                section_playback_time = 0
                for target_vertical in target_verticals:
                    duration = duration_summary.get(target_vertical.vertical_id, 0)
                    section_playback_time = section_playback_time + duration
                    total_playback_time = total_playback_time + duration
                    # Playback Time for each vertical
                    record[target_vertical.column_name] = \
                        datetime_utils.seconds_to_time_format(duration) if duration else ''
                    chapter_name = target_vertical.chapter_name
                # Playback Time for each section
                record[u'{}{}{}'.format(
                    chapter_name,
                    AchievementStoreBase.FIELD_DELIMITER,
                    _(GaPlaybackStatusReportRecord.FIELD_SECTION_PLAYBACK_TIME))
                ] = datetime_utils.seconds_to_time_format(section_playback_time)

            # Total Playback Time
            record[_(GaPlaybackStatusReportRecord.FIELD_TOTAL_PLAYBACK_TIME)] = \
                datetime_utils.seconds_to_time_format(total_playback_time)

            records.append(record)
            task_progress.succeeded += 1
    except CourseDoesNotExist:
        TASK_LOG.warning(u"This course does not exist in modulestore. course_id={}".format(unicode(course_key)))
        task_progress.failed += 1
        return task_progress.update_task_state(extra_meta={'step': 'Not exist course'})
    except Exception as ex:
        TASK_LOG.error(u"Unexpected error occurred: {}".format(ex))
        task_progress.failed += 1
        return task_progress.update_task_state(extra_meta={'step': 'Error'})

    TASK_LOG.info(u'{}, Task type: {}, Playback calculation completed for students: {}/{}'.format(
        task_info_string,
        action_name,
        student_counter,
        total_students
    ))

    __, rows = format_dictlist(records, header)
    rows.insert(0, header)

    current_step = {'step': 'Uploading CSV'}
    task_progress.update_task_state(extra_meta=current_step)

    upload_csv_to_report_store(rows, 'playback_status_report', course_key, start_date)
    return task_progress.update_task_state(extra_meta=current_step)
