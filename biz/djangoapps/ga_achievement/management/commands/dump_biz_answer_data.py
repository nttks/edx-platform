"""
Management command to dump csv file of answer data.
"""
import argparse
import json
import logging
import os
import unicodecsv

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext as _

from biz.djangoapps.util import datetime_utils
from boto import connect_s3
from boto.s3.key import Key
from courseware.models import StudentModule
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from util.file import course_filename_prefix_generator
from xmodule.modulestore.django import modulestore

log = logging.getLogger(__name__)
DUMP_ANSWER_DATA_DIR_NAME = 'dump_biz_answer_data'
DUMP_ANSWER_DATA_FILE_NAME = 'dump_biz_answer_data'


class Command(BaseCommand):
    """
    Dump csv file of answer data.
    """
    help = """
    Usage: python manage.py lms --settings=aws dump_biz_answer_data <course_id>
    """

    def add_arguments(self, parser):
        parser.add_argument('args', nargs=argparse.REMAINDER)

    def handle(self, *args, **options):
        log.info(u"Command dump_biz_answer_data started at {}".format(datetime_utils.timezone_now()))

        if len(args) != 1:
            raise CommandError("This command requires one arguments: |<course_id>|")

        # Note: BaseCommand translations are deactivated by default, so activate here
        translation.activate(settings.LANGUAGE_CODE)
        # Check args
        try:
            course_key = CourseKey.from_string(args[0])
        except InvalidKeyError:
            raise CommandError(
                "The course_id is not of the right format. It should be like 'course-v1:org+course+run'")
        course = modulestore().get_course(course_key)
        if not course:
            raise CommandError("Course with {} key not found.".format(args[0]))

        header = [_('Username')]
        component_module_ids = []
        for chapter in course.get_children():
            chapter_name = chapter.display_name
            for section in chapter.get_children():
                section_name = section.display_name
                for vertical in section.get_children():
                    for component in vertical.get_children():
                        component_name = component.display_name
                        if component.location.category == 'problem':
                            header.append(create_column(chapter_name, section_name, component_name, _('Submit Count')))
                            header.append(create_column(chapter_name, section_name, component_name, _('Final Judgement')))
                            # Set 'module_id' for get record
                            component_module_ids.append(component.location)

        sms = StudentModule.objects.filter(
            course_id=course_key,
            module_type='course',
        ).order_by('student_id')

        rows = []
        for sm in sms:
            user = User.objects.get(id=sm.student_id)
            row = [user.username]
            for component_module_id in component_module_ids:
                try:
                    student_answer = StudentModule.objects.get(
                        course_id=course_key,
                        module_type='problem',
                        module_state_key=component_module_id,
                        student=sm.student_id,
                    )
                except StudentModule.DoesNotExist:
                    # attempts column set blank
                    row.append('')
                    # correctness column set blank
                    row.append('')
                    continue

                state_dict = json.loads(student_answer.state)
                # attempts
                row.append(state_dict.get('attempts', ''))
                # correctness
                if 'correct_map' in state_dict.keys():
                    correct_count = 0
                    for k, v in state_dict['correct_map'].iteritems():
                        if v['correctness'] == 'correct':
                            correct_count += 1
                    row.append(u'{}({})'.format(correct_count, len(state_dict['correct_map'])))
                else:
                    row.append('')

            # Add user data
            rows.append(row)

        # S3 store
        try:
            conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
            bucket = conn.get_bucket(settings.FILE_UPLOAD_STORAGE_BUCKET_NAME)
        except Exception as e:
            print e
            raise CommandError("Could not establish a connection to S3 for file upload. Check your credentials.")

        tmp_dir = '/tmp/{}'.format(DUMP_ANSWER_DATA_DIR_NAME)
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
        filename = '{course_prefix}_{csv_name}.csv'.format(
            course_prefix=course_filename_prefix_generator(course_key),
            csv_name=DUMP_ANSWER_DATA_FILE_NAME,
        )
        path = os.path.join(tmp_dir, filename)
        write_csv(path, header, rows)
        upload_file_to_s3(bucket, filename, path)

        # Delete temp file
        os.remove('{}/{}'.format(tmp_dir, filename))

        log.info(u"Command dump_biz_answer_data finished at {}".format(datetime_utils.timezone_now()))


def create_column(chapter_name, section_name, component_name, column_name):
    return u"{chapter}{delimiter}{section}{delimiter}{component}{delimiter}{column}".format(
        chapter=chapter_name,
        section=section_name,
        component=component_name,
        column=column_name,
        delimiter='___'
    )


def write_csv(filename, header, rows):
    try:
        with open(filename, 'wb') as output_file:
            writer = unicodecsv.writer(output_file, encoding='utf-8')
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
    except IOError:
        raise CommandError("Error writing to file: {}".format(filename))


def upload_file_to_s3(bucket, filename, path):
    try:
        s3key = Key(bucket)
        s3key.key = '{}/{}'.format(DUMP_ANSWER_DATA_DIR_NAME, filename)
        s3key.set_contents_from_filename(path)
    except:
        raise CommandError("Upload to S3 failed")
    finally:
        s3key.close()
