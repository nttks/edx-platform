"""
Student status export CSV file batch
"""
import time
import os
import json
import logging
import shutil
import unicodecsv as csv
from pytz import UTC

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import translation

from courseware.courses import get_course
from lms.djangoapps.courseware.ga_mongo_utils import PlaybackFinishStore
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from opaque_keys.edx.keys import UsageKey

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Usage: python manage.py lms --settings=aws output_student_module_status_csv --a <action_name> (--f <file_name> --d true)
    """

    ACTION_NAME_OUTPUT_MASTER = 'output_master'
    ACTION_NAME_OUTPUT_STATUS = 'output_status'

    TMP_DATA_MAX_NUM = 10000
    # dir path
    BASE_DIR = '/tmp/output_student_module_status_csv'
    FILE_DIR_ENROLLMENT = BASE_DIR + '/enrollment'
    FILE_DIR_COURSE = BASE_DIR + '/course'
    FILE_DIR_STUDENT = BASE_DIR + '/student'
    FILE_DIR_MODULE = BASE_DIR + '/module'
    FILE_DIR_MODULE_CREATED = BASE_DIR + '/module_created'
    # file path
    FILE_NAME_STUDENT = 'student_enrollment_status_'
    FILE_NAME_MODULE = 'student_enrollment_module_status_'
    # file header
    FILE_ENROLLMENT_HEADER = {
        'enroll_id': 0,
        'enroll_course_id': 1,
        'enroll_created': 2,
        'enroll_user_id': 3,
        'enroll_user_username': 4,
        'enroll_user_email': 5,
        'enroll_attr_value': 6
    }
    FILE_COURSE_HEADER = {
        'course_id': 0,
        'end': 1,
        'user_id': 2,
        'module_category': 3,
        'module_name': 4,
        'module_block_id': 5,
        'module_usage_key': 6,
        'module_modified': 7,
        'survey_created': 8,
        'video_status': 9,
        'video_change_time': 10,
    }
    # student csv keys
    STUDENT_KEY_STATUS = 'status'
    STUDENT_KEY_WORKING_DATE = 'working_date'
    STUDENT_KEY_WORKING_TIME = 'working_time'
    STUDENT_KEY_COMPLETED_DATE = 'completed_date'
    STUDENT_KEY_COMPLETED_TIME = 'completed_time'
    STUDENT_KEY_CLOSING_DATE = 'closing_date'
    STUDENT_KEY_CLOSING_TIME = 'closing_time'
    STUDENT_KEYS = (
        STUDENT_KEY_STATUS, STUDENT_KEY_WORKING_DATE, STUDENT_KEY_WORKING_TIME, STUDENT_KEY_COMPLETED_DATE,
        STUDENT_KEY_COMPLETED_TIME, STUDENT_KEY_CLOSING_DATE, STUDENT_KEY_CLOSING_TIME
    )
    # student status value
    STATUS_WAITING = '3'
    STATUS_WORKING = '4'
    STATUS_COMPLETED = '5'
    STATUS_CLOSING = '6'
    # module csv key
    MODULE_KEY_ID = 'id'
    MODULE_KEY_NAME = 'name'
    MODULE_KEY_STATUS = 'status'
    MODULE_KEY_STATUS_DATE = 'status_date'
    MODULE_KEY_STATUS_TIME = 'status_time'
    MODULE_KEYS = (
        MODULE_KEY_ID, MODULE_KEY_NAME, MODULE_KEY_STATUS, MODULE_KEY_STATUS_DATE, MODULE_KEY_STATUS_TIME
    )
    # module status value
    MODULE_STATUS_ON = '1'
    MODULE_STATUS_OFF = '0'
    MODULE_STATUS_NON = 'Null'

    def add_arguments(self, parser):
        parser.add_argument('-a', '--action', action="store", help='Please set "output_master" or "output_status"',)
        parser.add_argument('-f', '--filename', action="store", help='Please set file name for "output_status"',)
        parser.add_argument('-d', '--debug', default=False, action='store', help='Output debug log')
        pass

    def handle(self, *args, **options):
        if options['debug']:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)

        action_name = options['action'] if 'action' in options else ''
        log.info('output_student_module_status_csv command start {}'.format(action_name))

        log.info('execute start {}'.format(action_name))
        if action_name == self.ACTION_NAME_OUTPUT_MASTER:
            self.execute_output_master()

        elif action_name == self.ACTION_NAME_OUTPUT_STATUS:
            filename = options['filename'] if 'filename' in options else ''
            if os.path.exists(self.FILE_DIR_ENROLLMENT + '/' + filename):
                self.execute_output_csv(filename)
            else:
                log.error('{} file not found.'.format(filename))
        else:
            log.info('{} action not found.'.format(options['action'] if options['action'] else ''))

        log.info('output_student_module_status_csv command end {}'.format(action_name))

    def execute_output_master(self):
        translation.activate('ja')
        now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        playback_store = PlaybackFinishStore()

        # Check dir base
        if not os.path.exists(self.BASE_DIR):
            os.mkdir(self.BASE_DIR)
        # Refresh tmp dir
        if os.path.exists(self.FILE_DIR_ENROLLMENT):
            shutil.rmtree(self.FILE_DIR_ENROLLMENT)
        if os.path.exists(self.FILE_DIR_COURSE):
            shutil.rmtree(self.FILE_DIR_COURSE)
        if os.path.exists(self.FILE_DIR_MODULE_CREATED):
            shutil.rmtree(self.FILE_DIR_MODULE_CREATED)
        os.mkdir(self.FILE_DIR_ENROLLMENT)
        os.mkdir(self.FILE_DIR_COURSE)
        os.mkdir(self.FILE_DIR_MODULE_CREATED)

        # Write to csv
        target_course_ids = []
        for course_overview in CourseOverview.get_all_courses():
            # Check course pre open
            if course_overview.start and course_overview.start > now:
                continue
            # Check course end + 1 day
            if course_overview.end and (course_overview.end + timedelta(days=1)).strftime('%Y-%m-%d') < now.strftime('%Y-%m-%d'):
                continue

            try:
                course = get_course(course_overview.id)
            except Exception as e:
                log.info(e)
                continue

            if course.is_status_managed:
                target_course_ids.append(course_overview.id)
                timer = time.time()
                with open('{}/{}.csv'.format(self.FILE_DIR_COURSE, str(course.id)), 'w') as course_file:
                    course_file_writer = csv.writer(course_file, delimiter=',', quotechar=',')
                    self._write_course_info(course_file_writer, course, playback_store)
                log.debug('{} write to course csv time: {}'.format(course_overview.id, time.time() - timer))
                timer = time.time()
                with open('{}/{}.csv'.format(
                        self.FILE_DIR_MODULE_CREATED, str(course.id)), 'w') as module_created_file:
                    module_created_file_writer = csv.writer(module_created_file, delimiter=',', quotechar=',')
                    module_created_file_writer.writerows(self._get_students_module_created(str(course.id)))
                log.debug('{} write to module status csv time: {}'.format(course_overview.id, time.time() - timer))

        # Output csv 'CourseEnrollment'
        timer = time.time()
        with open(self.FILE_DIR_ENROLLMENT + '/enrollment.csv', 'w') as enrollment_file:
            enrollment_file_writer = csv.writer(enrollment_file, delimiter=',', quotechar=',')
            for enrollment in self._get_enrollments(target_course_ids):
                # Set EnrollmentAttribute value
                attr_value_attended = None
                attr_value_completed = None
                if enrollment[6]:
                    attr_value = json.loads(enrollment[6])
                    if 'attended_date' in attr_value:
                        attr_value_attended = attr_value['attended_date']
                    if 'completed_date' in attr_value:
                        attr_value_completed = attr_value['completed_date']

                enrollment_file_writer.writerow([
                    enrollment[0], enrollment[1], enrollment[2], enrollment[3], enrollment[4], enrollment[5],
                    attr_value_attended, attr_value_completed,
                ])
        log.debug('write to enrollment csv time: {}'.format(time.time() - timer))

    def _write_course_info(self, course_file_writer, course, playback_finish_store):
        unicode_course_id = unicode(course.id)
        video_all_modules = None

        for chapter in course.get_children():
            for section in chapter.get_children():
                for vertical in section.get_children():
                    for module in vertical.get_children():
                        if hasattr(module, 'is_status_managed') and module.is_status_managed:
                            if module.location.category == 'problem':
                                for problem in self._get_problem_module(
                                        UsageKey.from_string(module.location.to_deprecated_string()),
                                        unicode_course_id):
                                    course_file_writer.writerow(self._format_row_for_course_info(
                                        course_id=course.id, end=course.end, user_id=problem[0],
                                        module_category=module.location.category, module_name=module.display_name,
                                        module_block_id=module.location.block_id,
                                        module_usage_key=UsageKey.from_string(module.location.to_deprecated_string()),
                                        module_modified=problem[1]
                                    ))

                            elif module.location.category == 'html':
                                for survey in self._get_survey(
                                        unicode_course_id, unicode(vertical.location.block_id)):
                                    course_file_writer.writerow(self._format_row_for_course_info(
                                        course_id=course.id, end=course.end, user_id=survey[0],
                                        module_category=module.location.category, module_name=module.display_name,
                                        module_block_id=module.location.block_id,
                                        module_usage_key=UsageKey.from_string(module.location.to_deprecated_string()),
                                        survey_created=survey[1],
                                    ))

                            elif module.location.category in ['video', 'jwplayerxblock']:
                                # get playback finish status
                                if video_all_modules is None:
                                    video_all_modules = playback_finish_store.find_status_data_by_course_id(
                                        unicode_course_id)

                                for video in video_all_modules:
                                    for video_module in video['module_list']:
                                        if video_module['block_id'] == module.location.block_id:
                                            course_file_writer.writerow(self._format_row_for_course_info(
                                                course_id=course.id, end=course.end,
                                                user_id=video['user_id'], module_category=module.location.category,
                                                module_name=module.display_name, module_block_id=module.location.block_id,
                                                module_usage_key=UsageKey.from_string(
                                                    module.location.to_deprecated_string()),
                                                video_status=video_module['status'],
                                                video_change_time=video_module['change_time'],
                                            ))

                            elif module.location.category == 'survey':
                                for survey in self._get_survey_module(
                                        UsageKey.from_string(module.location.to_deprecated_string()),
                                        unicode_course_id):
                                    try:
                                        tmp_state = json.loads(survey[2])
                                        survey_submission_count = tmp_state['submissions_count']
                                    except (AttributeError, ValueError, KeyError):
                                        survey_submission_count = 0

                                    if survey_submission_count > 0:
                                        course_file_writer.writerow(self._format_row_for_course_info(
                                            course_id=course.id, end=course.end, user_id=survey[0],
                                            module_category=module.location.category, module_name=module.display_name,
                                            module_block_id=module.location.block_id,
                                            module_usage_key=UsageKey.from_string(
                                                module.location.to_deprecated_string()),
                                            module_modified=survey[1]
                                        ))

                            elif module.location.category == 'freetextresponse':
                                for free_text_response in self._get_freetextresponse_module(
                                        UsageKey.from_string(module.location.to_deprecated_string()),
                                        unicode_course_id):
                                    try:
                                        tmp_state = json.loads(free_text_response[2])
                                        attempts_count = tmp_state['count_attempts']
                                    except (AttributeError, ValueError, KeyError):
                                        attempts_count = 0

                                    if attempts_count > 0:
                                        course_file_writer.writerow(self._format_row_for_course_info(
                                            course_id=course.id, end=course.end, user_id=free_text_response[0],
                                            module_category=module.location.category, module_name=module.display_name,
                                            module_block_id=module.location.block_id,
                                            module_usage_key=UsageKey.from_string(
                                                module.location.to_deprecated_string()),
                                            module_modified=free_text_response[1]
                                        ))

    def _get_problem_module(self, module_id, course_id):
        with connection.cursor() as cursor:
            sql = """
            SELECT
                module.student_id,
                module.modified
            FROM
              courseware_studentmodule as module
            WHERE 
              module.module_id = %s AND
              module.module_type = 'problem' AND
              module.course_id = %s AND 
              module.grade is NOT NULL 
            ORDER BY
              module.created desc 
            """
            cursor.execute(sql, [str(module_id), course_id])
            student_modules = cursor.fetchall()
            cursor.execute('UNLOCK TABLES')
        return student_modules

    def _get_survey_module(self, module_id, course_id):
        with connection.cursor() as cursor:
            sql = """
            SELECT
                module.student_id,
                module.modified,
                module.state
            FROM
              courseware_studentmodule as module
            WHERE 
              module.module_id = %s AND
              module.module_type = 'survey' AND
              module.course_id = %s
            ORDER BY
              module.created desc 
            """
            cursor.execute(sql, [str(module_id), course_id])
            student_modules = cursor.fetchall()
            cursor.execute('UNLOCK TABLES')
        return student_modules

    def _get_freetextresponse_module(self, module_id, course_id):
        with connection.cursor() as cursor:
            sql = """
            SELECT
                module.student_id,
                module.modified,
                module.state
            FROM
              courseware_studentmodule as module
            WHERE 
              module.module_id = %s AND
              module.module_type = 'freetextresponse' AND
              module.course_id = %s
            ORDER BY
              module.created desc 
            """
            cursor.execute(sql, [str(module_id), course_id])
            student_modules = cursor.fetchall()
            cursor.execute('UNLOCK TABLES')
        return student_modules

    def _get_survey(self, course_id, block_id):
        with connection.cursor() as cursor:
            sql = """
            SELECT
                survey.user_id,
                survey.created
            FROM
              ga_survey_surveysubmission as survey
            WHERE 
              survey.course_id = %s AND
              survey.unit_id = %s
            ORDER BY
              survey.created desc 
            """
            cursor.execute(sql, [course_id, block_id])
            survey = cursor.fetchall()
            cursor.execute('UNLOCK TABLES')
        return survey

    def _get_enrollments(self, course_ids):
        if len(course_ids) is 0:
            return []

        timer = time.time()
        with connection.cursor() as cursor:
            sql = """
            SELECT
             enrollment.id,
             enrollment.course_id,
             enrollment.created,
             user.id,
             user.username,
             user.email,
             attr.value
            FROM
             student_courseenrollment as enrollment
            INNER JOIN auth_user as user ON enrollment.user_id = user.id
            LEFT OUTER JOIN (
                SELECT enrollment_id, MIN(value) as value
                FROM student_courseenrollmentattribute
                WHERE namespace = 'ga'
                AND name = 'attended_status'
                GROUP BY enrollment_id
            ) as attr ON attr.enrollment_id = enrollment.id
            WHERE user.is_staff = 0 AND user.is_superuser = 0 AND enrollment.course_id in %s
            ORDER BY enrollment.course_id
            """
            cursor.execute(sql, [course_ids])
            enrollments = cursor.fetchall()
            cursor.execute('UNLOCK TABLES')
        log.debug('student_courseenrollment count:{}'.format(str(len(enrollments))))
        log.debug('student_courseenrollment time:{}'.format(time.time() - timer))
        return enrollments

    def execute_output_csv(self, filename):
        translation.activate('ja')
        now = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        now_str = now.strftime('%Y-%m-%d %H:%M:%S') + '+00:00'

        # Dir refresh
        filename_suffix = (now + timedelta(hours=9)).strftime('%Y%m%d') + '_' + filename[-2:] + '.csv'
        filename_student = '/' + self.FILE_NAME_STUDENT + filename_suffix
        filename_module = '/' + self.FILE_NAME_MODULE + filename_suffix
        if not os.path.exists(self.FILE_DIR_STUDENT):
            os.mkdir(self.FILE_DIR_STUDENT)
        if not os.path.exists(self.FILE_DIR_MODULE):
            os.mkdir(self.FILE_DIR_MODULE)

        # Open file
        with open(self.FILE_DIR_STUDENT + filename_student, 'w') as student_file:
            student_file_writer = csv.writer(student_file, delimiter=',', quotechar=',')
            with open(self.FILE_DIR_MODULE + filename_module, 'w') as module_file:
                module_file_writer = csv.writer(module_file, delimiter=',', quotechar=',')

                with open(self.FILE_DIR_ENROLLMENT + '/' + filename, 'r') as enrollment_file:
                    enrollments = enrollment_file.readlines()

                # for loop
                current_course_id = None
                course_end = None
                modules = []
                modules_created = None
                # for write to csv
                tmp_module_write_data, tmp_module_write_data_counter = [], 0
                tmp_student_write_data, tmp_student_write_data_counter = [], 0

                enrollment_timer = time.time()
                for i, row in enumerate(enrollments):
                    if i % 10000 == 0:
                        log.debug('{} : enrollment finished : {} : {}'.format(
                            filename, str(i), time.time() - enrollment_timer))
                        enrollment_timer = time.time()

                    enroll = [s.strip() for s in row.split(',')]
                    enroll_id = enroll[0]
                    enroll_course_id = enroll[1]
                    enroll_created = enroll[2]
                    enroll_user_id = enroll[3]
                    enroll_user_username = enroll[4]
                    enroll_user_email = enroll[5]
                    enroll_attr_value_attended = enroll[6]
                    enroll_attr_value_completed = enroll[7]

                    # first time at loop or different course from the last time
                    # get course and module created
                    if current_course_id is None or current_course_id != enroll_course_id:
                        current_course_id, course_end, modules = self._get_course_info_from_file(enroll_course_id)
                        modules_created = self._get_students_module_created_from_file(enroll_course_id)

                    # Initialize dict for write student file
                    student_status = {key: '' for key in self.STUDENT_KEYS}
                    # get module created
                    module_created = self._str_to_datetime(
                        modules_created[enroll_user_id]) if enroll_user_id in modules_created else None

                    # Check is attended
                    if not module_created and not enroll_attr_value_attended:
                        student_status[self.STUDENT_KEY_STATUS] = self.STATUS_WAITING
                        if course_end and course_end < now_str:
                            student_status[self.STUDENT_KEY_STATUS] = self.STATUS_CLOSING
                            self._set_date_time(self._str_to_datetime(course_end), student_status, 'closing')

                        tmp_student_write_data.append(self._create_students_data(
                            course_id=enroll_course_id, user_id=enroll_user_id, username=enroll_user_username,
                            email=enroll_user_email, **student_status))
                        tmp_student_write_data_counter += 1
                        continue

                    # Check status date of attended date and completed date
                    attended_datetime = self._str_to_datetime(
                        enroll_attr_value_attended, '%Y-%m-%dT%H:%M:%S.%f') if enroll_attr_value_attended else None
                    completed_datetime = self._str_to_datetime(
                        enroll_attr_value_completed, '%Y-%m-%dT%H:%M:%S.%f') if enroll_attr_value_completed else None

                    # Check status working or completed
                    for module_block_id in modules:
                        module = modules[module_block_id]
                        module_status = {key: '' for key in self.MODULE_KEYS}
                        module_status[self.MODULE_KEY_ID] = module['module_block_id']
                        module_status[self.MODULE_KEY_NAME] = module['display_name']

                        if module['category'] == 'html':
                            if enroll_user_id in module['html_survey_modules']:
                                self._set_date_time(
                                    self._str_to_datetime(module['html_survey_modules'][enroll_user_id]),
                                    module_status, 'status'
                                )
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_ON
                            else:
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_OFF

                        elif module['category'] == 'problem':
                            if enroll_user_id in module['problem_modules']:
                                self._set_date_time(
                                    self._str_to_datetime(module['problem_modules'][enroll_user_id]),
                                    module_status,
                                    'status'
                                )
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_ON
                            else:
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_OFF

                        elif module['category'] in ['video', 'jwplayerxblock']:
                            if enroll_user_id in module['video_modules']:
                                video_module = module['video_modules'][enroll_user_id]
                                self._set_date_time(self._str_to_datetime(
                                    video_module['change_time']), module_status, 'status')
                                if video_module['status'] == 'True':
                                    module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_ON
                                else:
                                    module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_OFF
                            else:
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_NON

                        elif module['category'] == 'survey':
                            if enroll_user_id in module['survey_modules']:
                                self._set_date_time(
                                    self._str_to_datetime(module['survey_modules'][enroll_user_id]),
                                    module_status,
                                    'status'
                                )
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_ON
                            else:
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_OFF
                                working_flag = True

                        elif module['category'] == 'freetextresponse':
                            if enroll_user_id in module['freetextresponse_modules']:
                                self._set_date_time(
                                    self._str_to_datetime(module['freetextresponse_modules'][enroll_user_id]),
                                    module_status,
                                    'status'
                                )
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_ON
                            else:
                                module_status[self.MODULE_KEY_STATUS] = self.MODULE_STATUS_OFF
                                working_flag = True

                        # Set to tmp data for write
                        tmp_module_write_data.append(self._create_modules_data(
                            course_id=enroll_course_id, user_id=enroll_user_id, username=enroll_user_username,
                            email=enroll_user_email, **module_status))
                        tmp_module_write_data_counter += 1

                    if modules and len(modules) > 0:
                        most_before = self._managed_working_date(module_created, attended_datetime)
                        self._set_date_time(most_before, student_status, 'working')
                        if not completed_datetime:
                            if course_end and course_end < now_str:
                                student_status[self.STUDENT_KEY_STATUS] = self.STATUS_CLOSING
                                self._set_date_time(self._str_to_datetime(course_end), student_status, 'closing')
                            else:
                                student_status[self.STUDENT_KEY_STATUS] = self.STATUS_WORKING
                        else:
                            student_status[self.STUDENT_KEY_STATUS] = self.STATUS_COMPLETED
                            self._set_date_time(completed_datetime, student_status, 'completed')
                    else:
                        self._set_date_time(
                            self._str_to_datetime(enroll_created), student_status, 'working')
                        if course_end and course_end < now_str:
                            student_status[self.STUDENT_KEY_STATUS] = self.STATUS_CLOSING
                            self._set_date_time(self._str_to_datetime(course_end), student_status, 'closing')
                        else:
                            student_status[self.STUDENT_KEY_STATUS] = self.STATUS_WORKING

                    # Set to tmp data for write
                    tmp_student_write_data.append(self._create_students_data(
                        course_id=enroll_course_id, user_id=enroll_user_id, username=enroll_user_username,
                        email=enroll_user_email, **student_status))
                    tmp_student_write_data_counter += 1

                    # Write to file ato TMP_DATA_MAX_NUM
                    if tmp_module_write_data_counter >= self.TMP_DATA_MAX_NUM:
                        module_file_writer.writerows(tmp_module_write_data)
                        tmp_module_write_data = []
                        tmp_module_write_data_counter = 0

                    if tmp_student_write_data_counter >= self.TMP_DATA_MAX_NUM:
                        student_file_writer.writerows(tmp_student_write_data)
                        tmp_student_write_data = []
                        tmp_student_write_data_counter = 0

                # Write csv
                if len(tmp_module_write_data) != 0:
                    module_file_writer.writerows(tmp_module_write_data)
                if len(tmp_student_write_data) != 0:
                    student_file_writer.writerows(tmp_student_write_data)

            log.info('end write to student and module csv.')

    def _get_course_info_from_file(self, course_id):
        modules = {}
        course_info_acquired_flag = False
        course_end = ''
        with open('{}/{}.csv'.format(self.FILE_DIR_COURSE, course_id), 'r') as modules_file:
            for module_str in modules_file:
                module_row = [s.strip() for s in module_str.split(',')]
                module_dict = {item[0]: module_row[item[1]] for item in self.FILE_COURSE_HEADER.items()}
                module_block_id = module_dict['module_block_id']
                user_id = module_dict['user_id']

                if not course_info_acquired_flag:
                    course_end = module_dict['end']

                # set initialize
                if module_block_id not in modules:
                    modules[module_block_id] = {
                        'category': module_dict['module_category'],
                        'display_name': module_dict['module_name'],
                        'module_block_id': module_dict['module_block_id'],
                        'problem_modules': {},
                        'html_survey_modules': {},
                        'video_modules': {},
                        'survey_modules': {},
                        'freetextresponse_modules': {},
                    }

                if module_dict['module_category'] == 'problem':
                    modules[module_block_id]['problem_modules'][user_id] = module_dict['module_modified']

                elif module_dict['module_category'] == 'html':
                    modules[module_block_id]['html_survey_modules'][user_id] = module_dict['survey_created']

                elif module_dict['module_category'] in ['video', 'jwplayerxblock']:
                    modules[module_block_id]['video_modules'][user_id] = {
                        'status': module_dict['video_status'],
                        'change_time': module_dict['video_change_time']
                    }

                elif module_dict['module_category'] == 'survey':
                    modules[module_block_id]['survey_modules'][user_id] = module_dict['module_modified']

                elif module_dict['module_category'] == 'freetextresponse':
                    modules[module_block_id]['freetextresponse_modules'][user_id] = module_dict['module_modified']

        return course_id, course_end, modules

    def _get_students_module_created_from_file(self, course_id):
        module_created_dict = {}
        with open('{}/{}.csv'.format(self.FILE_DIR_MODULE_CREATED, course_id), 'r') as module_created_file:
            for module_created_str in module_created_file:
                row = [s.strip() for s in module_created_str.split(',')]
                module_created_dict[row[0]] = row[1]
        return module_created_dict

    def _format_row_for_course_info(
            self, course_id, end, user_id, module_category, module_name, module_block_id,
            module_usage_key, module_modified='', survey_created='', video_status='', video_change_time=''):
        return [
            unicode(course_id), str(end), str(user_id), module_category, module_name, module_block_id,
            module_usage_key, module_modified, survey_created, video_status, video_change_time
        ]

    def _get_students_module_created(self, course_id):
        with connection.cursor() as cursor:
            sql = """
            SELECT
                student_id,
                created
            FROM
              courseware_studentmodule
            WHERE 
              course_id = %s
            GROUP BY
              created
            """
            cursor.execute(sql, [course_id])
            student_modules = cursor.fetchall()
            cursor.execute("UNLOCK TABLES")
        return student_modules

    def _str_to_datetime(self, datetime_str, str_format=None):
        try:
            if len(datetime_str) > 25:
                # exists millisecond
                if str_format:
                    return UTC.localize(datetime.strptime(datetime_str[:-6], str_format))
                else:
                    return UTC.localize(datetime.strptime(datetime_str[:-6], '%Y-%m-%d %H:%M:%S.%f'))
            else:
                # not exists millisecond
                return UTC.localize(datetime.strptime(datetime_str[:-6], '%Y-%m-%d %H:%M:%S'))
        except Exception as e:
            log.error(e)
            log.error(datetime_str)
            return None

    def _set_date_time(self, target_datetime, data_status, key):
        if target_datetime:
            target_datetime = target_datetime + timedelta(hours=9)
            data_status[key + '_date'] = target_datetime.strftime('%Y-%m-%d')
            data_status[key + '_time'] = target_datetime.strftime('%H:%M:%S.%f') + '+09:00'
        return data_status

    def _create_students_data(self, course_id, user_id, username, email, **student):
        return [
            str(course_id), str(user_id), username, email, student[self.STUDENT_KEY_STATUS],
            student[self.STUDENT_KEY_WORKING_DATE], student[self.STUDENT_KEY_WORKING_TIME],
            student[self.STUDENT_KEY_COMPLETED_DATE], student[self.STUDENT_KEY_COMPLETED_TIME],
            student[self.STUDENT_KEY_CLOSING_DATE], student[self.STUDENT_KEY_CLOSING_TIME],
        ]

    def _create_modules_data(self, course_id, user_id, username, email, **module_status):
        return [
            str(course_id), str(user_id), username, email, module_status[self.MODULE_KEY_ID],
            module_status[self.MODULE_KEY_NAME], module_status[self.MODULE_KEY_STATUS],
            module_status[self.MODULE_KEY_STATUS_DATE], module_status[self.MODULE_KEY_STATUS_TIME]
        ]

    def _managed_working_date(self, module_created, attended_datetime):
        module_min = module_created if module_created else None
        attr_min = attended_datetime if attended_datetime is not None else None
        if module_min is None and attr_min is None:
            return ''
        elif module_min is not None and attr_min is None:
            return module_min
        elif module_min is None and attr_min is not None:
            return attr_min
        else:
            return module_min if str(module_min)[:-6] < str(attr_min)[:-7] else attr_min
