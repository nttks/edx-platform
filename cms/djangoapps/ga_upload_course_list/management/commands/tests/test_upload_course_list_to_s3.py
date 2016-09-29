from copy import copy
from datetime import datetime, timedelta
import json
from mock import patch
import pytz
from StringIO import StringIO
import unittest

from nose.plugins.attrib import attr

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from ga_upload_course_list.management.commands import upload_course_list_to_s3 as cc

from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


class UploadToS3CommandTestCase(TestCase):

    def setUp(self):
        self.args = []
        self.kwargs = {"template_only": False, "category": None}

        patcher = patch(
            'ga_upload_course_list.management.commands.upload_course_list_to_s3.CourseList')
        self.clist_m = patcher.start()
        self.addCleanup(patcher.stop)

    def test_handle(self):
        cc.Command().handle(*self.args, **self.kwargs)

        self.clist_m.assert_called_once_with(target_category=self.kwargs["category"])
        self.clist_m().upload.assert_called_once_with(self.kwargs["template_only"])


@unittest.skip("TODO: after release Dogwood")
@override_settings(
    TOP_PAGE_BUCKET_NAME="bucket", AWS_ACCESS_KEY_ID="akey",
    AWS_SECRET_ACCESS_KEY="skey")
class UploadToS3CommandIntegrationTestCase(ModuleStoreTestCase):

    def setUp(self):
        super(UploadToS3CommandIntegrationTestCase, self).setUp()
        self.prog_name = 'upload_course_list_to_s3'
        self.args = []
        self.kwargs = {"template_only": False, "category": None}
        self.kwargs_use_template_only = {"template_only": True, "category": None}
        self.kwargs_use_category = {"template_only": False, "category": "category"}
        self.filename = 'test-image.gif'
        self.image_data = 'GIF87a-dummy'

        default_course_args = {
            'org': "org",
            'number': "cn1",
            'run': "run",
            'course_canonical_name': 'cname',
            'course_contents_provider': 'univ',
            'teacher_name': 'teacher',
            'course_span': 'span',
            'is_f2f_course': False,
            'short_description': 'short description!',
            'course_image': self.filename,
            'start': datetime(2015, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'end': datetime(2020, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'enrollment_start': datetime(2014, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'enrollment_end': datetime(2018, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'deadline_start': datetime(2019, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'terminate_start': datetime(2030, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
            'course_category': [],
            'course_card_path': 'course_card_path',
            'course_list_description': 'course_list_description',
        }

        def create_course(update_course_args):
            course_args = copy(default_course_args)
            course_args.update(update_course_args)
            course = CourseFactory.create(**course_args)
            loc = StaticContent.compute_location(course.location.course_key, self.filename)
            content = StaticContent(loc, self.filename, 'image/gif', StringIO(self.image_data))
            contentstore().save(content)
            course.save()
            return course

        # opened
        self.course_cn1 = create_course({
            'number': "cn1",
            'course_category': ['cat1'],
            'course_canonical_name': '',
        })
        # no output
        self.course_cn2 = create_course({
            'number': "cn2",
            'course_category': [],
        })
        # opened f2f, 2 outputs
        self.course_cn3 = create_course({
            'number': "cn3",
            'course_category': ['cat1', 'cat2'],
            'start': datetime(2015, 1, 2, 0, 0, 0, tzinfo=pytz.utc),
            'is_f2f_course': True,
        })
        # no output
        self.course_cn4 = create_course({
            'number': "cn4",
            'course_category': ['cat1'],
            'enrollment_start': datetime(2030, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # no output
        self.course_cn5 = create_course({
            'number': "cn5",
            'course_category': ['cat1'],
            'terminate_start': datetime(2015, 2, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # when start ?, 2 outputs
        self.course_cn6 = create_course({
            'number': "cn6",
            'course_category': ['cat1', 'cat2'],
            'start': datetime(2030, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # recruit
        self.course_cn7 = create_course({
            'number': "cn7",
            'course_category': ['cat1'],
            'start': datetime(2017, 1, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # over deadline
        self.course_cn8 = create_course({
            'number': "cn8",
            'course_category': ['cat1'],
            'start': datetime(2015, 1, 3, 0, 0, 0, tzinfo=pytz.utc),
            'deadline_start': datetime(2015, 2, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # closed1
        self.course_cn9 = create_course({
            'number': "cn9",
            'course_category': ['cat1'],
            'end': datetime(2015, 3, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # closed2, 2 outputs
        self.course_cn10 = create_course({
            'number': "cn10",
            'course_category': ['cat1', 'cat2'],
            'start': datetime(2015, 1, 2, 0, 0, 0, tzinfo=pytz.utc),
            'end': datetime(2015, 3, 1, 0, 0, 0, tzinfo=pytz.utc),
        })
        # recent opened
        self.course_cn11 = create_course({
            'number': "cn11",
            'course_category': ['cat1'],
            'start': timezone.now() - timedelta(6),
        })

        patcher1 = patch(
            'ga_upload_course_list.views.S3Connection')
        self.s3conn = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch(
            'ga_upload_course_list.views.Key')
        self.s3key = patcher2.start()
        self.addCleanup(patcher2.stop)

        patcher3 = patch(
            'ga_upload_course_list.views.imghdr.what', return_value='gif')
        self.imghdr = patcher3.start()
        self.addCleanup(patcher3.stop)

    def assertEqualCourseDict(self, course_dict, course):
        if isinstance(course_dict, list) and isinstance(course, list):
            self.assertEqual(len(course_dict), len(course))
            for i in range(len(course_dict)):
                self.assertEqualCourseDict(course_dict[i], course[i])
            return
        self.assertEqual(course_dict['id'], course.id.to_deprecated_string())

    def test_upload(self):
        call_command(self.prog_name, *self.args, **self.kwargs)

        self.s3conn.assert_called_once_with(
            settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
        self.s3key().set_contents_from_string.assert_any_call(self.image_data)

        call_list = self.s3key().set_contents_from_string.call_args_list
        for args, kwargs in call_list:
            if args[0]:
                if self.image_data in args:
                    continue

                courses = json.loads(args[0])
                if 'recent_courses' in courses and 'opened_courses' in courses:
                    recent_courses = courses['recent_courses']
                    opened_courses = courses['opened_courses']
                    count_course = len(recent_courses) + len(opened_courses)
                    self.assertTrue(count_course > 0)
                    if count_course == 2:
                        # When Category is "cat2"
                        self.assertEqual(len(recent_courses), 1)
                        self.assertEqualCourseDict(recent_courses[0], self.course_cn6)
                        self.assertEqual(recent_courses[0]['start_date'], 'TBD')
                        self.assertEqual(len(opened_courses), 1)
                        self.assertEqualCourseDict(opened_courses[0], self.course_cn3)
                        self.assertTrue(opened_courses[0]['is_f2f_course'])
                    else:
                        # When Category is "cat1"
                        self.assertEqual(len(recent_courses), 3)
                        self.assertEqualCourseDict(recent_courses, [self.course_cn11, self.course_cn7, self.course_cn6])
                        self.assertEqual(recent_courses[2]['start_date'], 'TBD')
                        self.assertEqual(len(opened_courses), 3)
                        self.assertEqualCourseDict(opened_courses, [self.course_cn8, self.course_cn3, self.course_cn1])
                        self.assertNotEqual(opened_courses[2]['name'], '')
                    continue

                if 'opened_courses' in courses and 'closed_courses' in courses:
                    opened_courses = courses['opened_courses']
                    closed_courses = courses['closed_courses']
                    count_course = len(opened_courses) + len(closed_courses)
                    self.assertTrue(count_course > 0)
                    if count_course == 3:
                        # When Category is "cat2"
                        self.assertEqual(len(opened_courses), 2)
                        self.assertEqualCourseDict(opened_courses, [self.course_cn3, self.course_cn6])
                        self.assertTrue(opened_courses[0]['is_f2f_course'])
                        self.assertEqual(opened_courses[1]['start_date'], 'TBD')
                        self.assertEqual(len(closed_courses), 1)
                        self.assertEqualCourseDict(closed_courses[0], self.course_cn10)
                    else:
                        # When Category is "cat1"
                        self.assertEqual(len(opened_courses), 6)
                        self.assertEqualCourseDict(opened_courses, [self.course_cn1, self.course_cn3, self.course_cn8, self.course_cn11, self.course_cn7, self.course_cn6])
                        self.assertTrue(opened_courses[1]['is_f2f_course'])
                        self.assertNotEqual(opened_courses[0]['name'], '')
                        self.assertEqual(opened_courses[5]['start_date'], 'TBD')
                        self.assertEqual(len(closed_courses), 2)
                        self.assertEqualCourseDict(closed_courses, [self.course_cn10, self.course_cn9])
                    continue

                if 'archived_courses' in courses:
                    archived_courses = courses['archived_courses']
                    count_course = len(archived_courses)
                    self.assertTrue(count_course > 0)
                    if count_course == 1:
                        # When Category is "cat2"
                        self.assertEqual(len(archived_courses), 1)
                        self.assertEqualCourseDict(archived_courses, [self.course_cn10])
                    else:
                        # When Category is "cat1"
                        self.assertEqual(len(archived_courses), 3)
                        self.assertEqualCourseDict(archived_courses, [self.course_cn10, self.course_cn5, self.course_cn9])
                    continue

                self.fail(args[0])
