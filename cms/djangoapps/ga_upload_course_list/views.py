"""
upload course list
"""
from datetime import timedelta
import json
import logging
import os

from boto.s3 import connect_to_region
from boto.s3.connection import Location, OrdinaryCallingFormat
from boto.s3.key import Key
from boto.exception import S3ResponseError

from django.conf import settings
from django.utils import timezone

from openedx.core.djangoapps.models.course_details import CourseDetails

from xmodule.contentstore.django import contentstore
from xmodule.contentstore.content import StaticContent
from xmodule.exceptions import NotFoundError
from xmodule.modulestore.django import modulestore


log = logging.getLogger(__name__)
CATEGORY_DIR = 'data/course/'
IMAGE_DIR = 'images/course_card/'


class CourseListException(Exception):
    pass


class InvalidSettings(CourseListException):
    pass


class DuplicateDeclaration(CourseListException):
    pass


class CourseCardNotFound(CourseListException):
    pass


class CourseList(object):
    def __init__(self, target_category=None):
        self.store = S3Store()
        self.target_category = target_category
        self.base_now = timezone.now()
        self.module_store = modulestore()
        self.content_store = contentstore()

    def upload(self, template_only=False):
        courses = self.module_store.get_courses()
        courses = [self._set_course_contents(c) for c in filter(self._filter_courses, courses)]
        contents = self._categorize_courses(courses)

        upload_resource = self._create_templates(contents)

        if template_only is False:
            upload_resource.update(self._get_course_card(courses))

        self._upload_to_store(upload_resource)

        if self.target_category is None:
            self._delete_from_store(upload_resource)

    def _filter_courses(self, course):

        if not course.course_category:
            log.info("Filter course without category: {}".format(course.id))
            return False

        if course.enrollment_start is None or course.enrollment_start > self.base_now:
            log.info("Filter course before enrollment: {}".format(course.id))
            return False

        if self.target_category is not None:
            if self.target_category not in course.course_category:
                log.info("Filter course not in the target category: {}".format(course.id))
                return False

        log.info("Target course: {}".format(course.id))
        return True

    def _set_course_contents(self, course):
        if hasattr(course, "course_list_description"):
            raise DuplicateDeclaration('course_list_description is duplicated.')
        if hasattr(course, "course_card_path"):
            raise DuplicateDeclaration('course_card_path is duplicated.')
        if hasattr(course, "course_card_data"):
            raise DuplicateDeclaration('course_card_data is duplicated.')
        if hasattr(course, "course_dict"):
            raise DuplicateDeclaration('course_dict is duplicated.')

        course.course_list_description = self._get_short_description(course)

        with self.module_store.bulk_operations(course.location.course_key):
            try:
                course_image = self.content_store.find(
                    StaticContent.compute_location(
                        course.location.course_key,
                        course.course_image
                    ),
                )
                log.debug(course_image.data)
                course.course_card_path = IMAGE_DIR + course.id.to_deprecated_string() + os.path.splitext(course_image.location.path)[-1]
                course.course_card_data = course_image.data
            except NotFoundError:
                raise CourseCardNotFound('Course card is not found: {} {}'.format(
                    course.id, course.course_image))

        course.course_dict = self._course_to_dict(course)

        return course

    def _categorize_courses(self, courses):
        contents = {}

        for course in courses:
            for category in course.course_category:
                if category not in contents:
                    contents[category] = [course]
                else:
                    contents[category].append(course)

        return contents

    def _get_short_description(self, course):
        return CourseDetails.fetch(course.id).short_description

    def _get_course_card(self, courses):
        course_cards = {}
        for course in courses:
            course_cards.update({course.course_card_path: course.course_card_data})
        return course_cards

    def _create_templates(self, contents):
        templates = {}

        startdate_in_7days = self.base_now - timedelta(7)
        log.debug('startdate_in_7days {}'.format(startdate_in_7days))

        for category, courses in contents.items():
            if self.target_category and self.target_category != category:
                continue

            index_recent_courses = []
            index_opened_courses = []
            list_opened_courses = []
            list_closed_courses = []
            archive_courses = []

            for course in courses:
                if course.terminate_start is not None and course.terminate_start < self.base_now:
                    archive_courses.append(course)
                    log.debug('archive_courses {}'.format(course.id.to_deprecated_string()))
                elif course.has_ended():
                    list_closed_courses.append(course)
                    log.debug('list_closed {}'.format(course.id.to_deprecated_string()))
                    archive_courses.append(course)
                    log.debug('archive_courses {}'.format(course.id.to_deprecated_string()))
                else:
                    list_opened_courses.append(course)
                    log.debug('list_opened {}'.format(course.id.to_deprecated_string()))
                    if course.start is None or not course.has_started() or course.start > startdate_in_7days:
                        index_recent_courses.append(course)
                        log.debug('index_recent {}'.format(course.id.to_deprecated_string()))
                    else:
                        index_opened_courses.append(course)
                        log.debug('index_opened {}'.format(course.id.to_deprecated_string()))

            index_map = {
                "recent_courses": sorted([c.course_dict for c in index_recent_courses], key=lambda x: x["start_date"]),
                "opened_courses": sorted([c.course_dict for c in index_opened_courses], key=lambda x: x["start_date"], reverse=True)
            }
            list_map = {
                "opened_courses": sorted([c.course_dict for c in list_opened_courses], key=lambda x: x["start_date"]),
                "closed_courses": sorted([c.course_dict for c in list_closed_courses], key=lambda x: x["start_date"], reverse=True)
            }
            archive_map = {
                "archived_courses": sorted([c.course_dict for c in archive_courses], key=lambda x: x["start_date"], reverse=True)
            }

            template_path = CATEGORY_DIR + category + '_index.json'
            templates.update({template_path: json.dumps(index_map)})
            log.info('{},{}'.format(category, template_path))

            template_path = CATEGORY_DIR + category + '_list.json'
            templates.update({template_path: json.dumps(list_map)})
            log.info('{},{}'.format(category, template_path))

            template_path = CATEGORY_DIR + category + '_archive.json'
            templates.update({template_path: json.dumps(archive_map)})
            log.info('{},{}'.format(category, template_path))

        return templates

    def _course_to_dict(self, course):
        course_dict = {
            "id": course.id.to_deprecated_string(),
            "card_path": course.course_card_path,
            "name": course.course_canonical_name if course.course_canonical_name else course.display_name_with_default,
            "start_date": course.start_datetime_text(format_string='%Y/%m/%d'),
            "is_deadline": course.is_course_deadline(),
            "is_f2f_course": course.is_f2f_course,
            "teacher_name": course.teacher_name,
            "contents_provider": course.course_contents_provider,
            "description": course.course_list_description,
            "span": course.course_span,
            "category": course.course_category,
        }
        if course.has_ended():
            course_dict["status"] = "closed"
        elif course.has_started():
            course_dict["status"] = "opened"
        else:
            course_dict["status"] = "recruit"

        return course_dict

    def _upload_to_store(self, catalog):
        for path, data in catalog.items():
            self.store.save(path, data)

    def _delete_from_store(self, catalog):
        # delete only json-files without images of course-card.
        for s3object in self.store.list(prefix=CATEGORY_DIR):
            if s3object.name not in catalog.keys():
                log.info('delete object from s3: {}'.format(s3object.name))
                s3object.delete()


class S3Store(object):
    """S3 store."""
    def __init__(self):
        if settings.TOP_PAGE_BUCKET_NAME is None:

            raise InvalidSettings(
                "TOP_PAGE_BUCKET_NAME is None."
            )

        self.bucket_name = settings.TOP_PAGE_BUCKET_NAME
        self.access_key = settings.AWS_ACCESS_KEY_ID
        self.secret_key = settings.AWS_SECRET_ACCESS_KEY
        self.location = Location.APNortheast
        self.conn = self._connect()

    def _connect(self):
        return connect_to_region(
            self.location,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            calling_format=OrdinaryCallingFormat(),
        )

    def list(self, prefix):
        bucket = self.conn.get_bucket(self.bucket_name)
        return bucket.list(prefix=prefix)

    def save(self, objectpath, data):
        try:
            bucket = self.conn.get_bucket(self.bucket_name)
        except S3ResponseError as e:
            if e.status == 404:
                bucket = self.conn.create_bucket(
                    self.bucket_name,
                    location=self.location)
                log.info("Create bucket: %s", self.bucket_name)
            else:
                raise

        try:
            s3key = Key(bucket)
            s3key.key = objectpath

            log.info('Upload object to s3://{}/{}'.format(self.bucket_name, objectpath))
            s3key.set_contents_from_string(data)

        finally:
            s3key.close()
