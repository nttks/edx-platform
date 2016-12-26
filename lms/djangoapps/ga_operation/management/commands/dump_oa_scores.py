from datetime import datetime
import logging
import os
from prettytable import PrettyTable
import shutil
import tarfile
import tempfile
import unicodecsv as csv

from boto import connect_s3
from boto.s3.key import Key
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import UTC

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openassessment.ga_data import OraAggregateData
from student.models import user_by_anonymous_id
from xmodule.modulestore.django import modulestore


class Command(BaseCommand):
    """
    This command allows you to dump all openassessment submissions with some related data.

    Usage: python manage.py lms --settings=aws dump_oa_scores course-v1:edX+DemoX+Demo_Course

    Args:
        course_id (unicode): The ID of the course to the openassessment item exists in,
                             like 'org/course/run' or 'course-v1:org+course+run'
    """
    help = """Usage: dump_oa_scores [-d /tmp/dump_oa_scores] [-w] <course_id>"""

    def add_arguments(self, parser):
        parser.add_argument('course_id')
        parser.add_argument(
            '-d', '--dump-dir',
            action="store",
            dest='dump_dir',
            default=None,
            help='Directory in which csv file is to be dumped',
        )
        parser.add_argument(
            '-w', '--with-attachments',
            action="store_true",
            dest='with_attachments',
            default=False,
            help='Whether to gather submission attachments',
        )

    def handle(self, *args, **options):
        course_id = options['course_id']

        # Check args: course_id
        try:
            course_id = CourseKey.from_string(course_id)
        except InvalidKeyError:
            raise CommandError("The course_id is not of the right format. It should be like 'org/course/run' or 'course-v1:org+course+run'")
        if not modulestore().get_course(course_id):
            raise CommandError("No such course was found.")

        # S3 store
        try:
            conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
            bucket = conn.get_bucket(settings.FILE_UPLOAD_STORAGE_BUCKET_NAME)
        except Exception as e:
            print e
            raise CommandError("Could not establish a connection to S3 for file upload. Check your credentials.")

        # Dump directory
        dump_dir = options['dump_dir'] or '/tmp/dump_oa_scores'
        if not os.path.exists(dump_dir):
            os.makedirs(dump_dir)

        # Whether to gather attachments
        with_attachments = options['with_attachments']

        # Find openassessment items
        oa_items = modulestore().get_items(course_id, qualifiers={'category': 'openassessment'})
        if not oa_items:
            raise CommandError("No openassessment item was found.")
        oa_items = sorted(oa_items, key=lambda item: item.start or datetime(2030, 1, 1, tzinfo=UTC()))
        print "Openassessment item(s):"
        oa_output = PrettyTable(['#', 'Item ID', 'Title', 'Type'])
        oa_output.align = 'l'
        for i, oa_item in enumerate(oa_items):
            row = []
            row.append(i)
            row.append(oa_item.location)
            row.append(oa_item.title)
            # If ORA2 XBlock has staff-assessment, we regard that it does NOT have peer-assessment.
            row.append('Staff Assessment' if 'staff-assessment' in oa_item.assessment_steps else 'Peer Assessment')
            oa_output.add_row(row)
        print oa_output
        while True:
            try:
                selected = raw_input("Choose an openassessment item # (empty to cancel): ")
                if selected == '':
                    print "Cancelled."
                    return
                selected_oa_item = int(selected)
                oa_item = oa_items[selected_oa_item]
                break
            except (IndexError, ValueError):
                print "WARN: Invalid number was detected. Choose again."
                continue

        submissions, header, rows = OraAggregateData.collect_ora2_data(course_id, oa_item.location, user_by_anonymous_id)

        if not submissions:
            raise CommandError("No submission was found.")

        # Logging to console
        for submission in submissions:
            print 'submission_uuid=%s' % submission['uuid']

        # Add title of item to all rows
        header.insert(0, 'Title')
        for row in rows:
            row.insert(0, oa_item.title)

        # Create csv file
        csv_filename = 'oa_scores-%s-#%d.csv' % ('-'.join([course_id.org, course_id.course, course_id.run]), selected_oa_item)
        csv_filepath = os.path.join(dump_dir, csv_filename)
        write_csv(csv_filepath, header, rows)
        # Upload to S3
        upload_file_to_s3(bucket, csv_filename, csv_filepath)

        # Download images from S3
        if with_attachments:
            temp_dir = tempfile.mkdtemp()
            for submission in submissions:
                file_key = u"{prefix}/{student_id}/{course_id}/{item_id}".format(
                    prefix=settings.FILE_UPLOAD_STORAGE_PREFIX,
                    student_id=submission['student_id'],
                    course_id=course_id.to_deprecated_string(),
                    item_id=oa_item.location.to_deprecated_string(),
                )
                try:
                    key = bucket.get_key(file_key)
                except:
                    print "WARN: No such file in S3 [%s]" % file_key
                    continue
                user = user_by_anonymous_id(submission['student_id'])
                user_path = os.path.join(temp_dir, user.username)
                try:
                    key.get_contents_to_filename(user_path)
                except:
                    print "WARN: Could not download file from S3 [%s]" % file_key
                    continue
            # Compress and upload to S3
            tar_filename = 'oa_scores-%s-#%d.tar.gz' % ('-'.join([course_id.org, course_id.course, course_id.run]), selected_oa_item)
            tar_filepath = os.path.join(dump_dir, tar_filename)
            tar = tarfile.open(tar_filepath, 'w:gz')
            tar.add(temp_dir, arcname=tar_filename)
            shutil.rmtree(temp_dir)
            upload_file_to_s3(bucket, tar_filename, tar_filepath)


def write_csv(filepath, header, rows):
    try:
        with open(filepath, 'wb') as output_file:
            writer = csv.writer(output_file)
            writer.writerow(header)
            for row in rows:
                writer.writerow(row)
    except IOError:
        raise CommandError("Error writing to file: %s" % filepath)
    print "Successfully created csv file: %s" % filepath


def upload_file_to_s3(bucket, filename, filepath):
    try:
        s3key = Key(bucket)
        s3key.key = "dump_oa_scores/{0}".format(filename)
        s3key.set_contents_from_filename(filepath)
    except:
        raise
    finally:
        s3key.close()
    print "Successfully uploaded file to S3: %s/%s" % (bucket.name, s3key.key)
