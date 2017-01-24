from copy import copy
from datetime import datetime
import json
from mock import MagicMock, patch, ANY, create_autospec
import pytz

from boto.exception import S3ResponseError
from boto.s3.connection import S3Connection, Location

from nose.plugins.attrib import attr

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.test.utils import override_settings

from ga_upload_course_list.views import (
    CourseList, S3Store, InvalidSettings, DuplicateDeclaration, CourseCardNotFound,
    CATEGORY_DIR, IMAGE_DIR,
)
from xmodule.contentstore.content import StaticContent
from xmodule.modulestore.tests.factories import CourseFactory
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.django import modulestore


class CourseListTestCase(ModuleStoreTestCase):

    def setUp(self):
        super(CourseListTestCase, self).setUp()
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
            'course_image': '/tmp/course_image.jpg',
            'start': datetime(2015, 1, 4, 7, 17, 28, tzinfo=pytz.utc),
            'end': datetime(2015, 1, 31, 9, 12, 59, tzinfo=pytz.utc),
            'enrollment_start': datetime(2015, 1, 1, 12, 10, 15, tzinfo=pytz.utc),
            'enrollment_end': datetime(2013, 1, 30, 1, 10, 11, tzinfo=pytz.utc),
            'deadline_start': datetime(2013, 1, 31, 0, 0, 0, tzinfo=pytz.utc),
            'terminate_start': datetime(2030, 1, 31, 9, 12, 59, tzinfo=pytz.utc),
            'course_category': ['cat1'],
        }

        patcher = patch('ga_upload_course_list.views.S3Store')
        self.addCleanup(patcher.stop)
        self.s3store = patcher.start()

        course_args = copy(default_course_args)
        self.course = CourseFactory.create(**course_args)
        self.store = modulestore()

        course_args = copy(default_course_args)
        course_args.update({'course_category': [], 'number': 'cn2'})
        self.course_no_category = CourseFactory.create(**course_args)

        course_args = copy(default_course_args)
        course_args.update({'course_category': ['cat1', 'cat2'], 'number': 'cn3'})
        self.course_two_categories = CourseFactory.create(**course_args)

        course_args = copy(default_course_args)
        course_args.update(
            {'enrollment_start': datetime(2999, 1, 1, 0, 0, 0, tzinfo=pytz.utc), 'number': 'cn4'})
        self.course_not_start = CourseFactory.create(**course_args)

        course_args = copy(default_course_args)
        course_args.update({'terminate_start': datetime(2015, 1, 1, 0, 0, 0, tzinfo=pytz.utc), 'number': 'cn5'})
        self.course_terminated = CourseFactory.create(**course_args)

        self.courses = self.store.get_courses()

        self.course_list = CourseList()
        self.course_list.content_store.find = MagicMock(return_value=MagicMock())
        self.course_list_with_target = CourseList('cat2')
        self.course_list_with_target.content_store.find = MagicMock(return_value=MagicMock())

        self.user = AnonymousUser()

    @patch('ga_upload_course_list.views.CourseList._filter_courses')
    @patch('ga_upload_course_list.views.CourseList._set_course_contents')
    @patch('ga_upload_course_list.views.CourseList._categorize_courses')
    @patch('ga_upload_course_list.views.CourseList._create_templates')
    @patch('ga_upload_course_list.views.CourseList._get_course_card')
    @patch('ga_upload_course_list.views.CourseList._upload_to_store')
    @patch('ga_upload_course_list.views.CourseList._delete_from_store')
    def test_upload(self, dels_m, upls_m, getc_m, crea_m, cate_m, setcc_m, filt_m):
        self.course_list.upload()

        filt_m.assert_any_call(self.course)
        setcc_m.assert_any_call(self.course)
        cate_m.assert_called_once_with([setcc_m(c) for c in self.courses])
        crea_m.assert_called_once_with(cate_m())
        getc_m.assert_called_once_with([setcc_m(c) for c in self.courses])
        upls_m.assert_called_once_with(crea_m())
        dels_m.assert_called_once_with(crea_m())

    @patch('ga_upload_course_list.views.CourseList._filter_courses')
    @patch('ga_upload_course_list.views.CourseList._set_course_contents')
    @patch('ga_upload_course_list.views.CourseList._categorize_courses')
    @patch('ga_upload_course_list.views.CourseList._create_templates')
    @patch('ga_upload_course_list.views.CourseList._get_course_card')
    @patch('ga_upload_course_list.views.CourseList._upload_to_store')
    @patch('ga_upload_course_list.views.CourseList._delete_from_store')
    def test_upload_with_target_category(self, dels_m, upls_m, getc_m, crea_m, cate_m, setcc_m, filt_m):
        self.course_list_with_target.upload()

        filt_m.assert_any_call(self.course_two_categories)
        setcc_m.assert_any_call(self.course_two_categories)
        cate_m.assert_called_once_with([setcc_m(c) for c in self.courses])
        crea_m.assert_called_once_with(cate_m())
        getc_m.assert_called_once_with([setcc_m(c) for c in self.courses])
        upls_m.assert_called_once_with(crea_m())

        self.assertEquals(dels_m.call_count, 0)

    @patch('ga_upload_course_list.views.CourseList._filter_courses')
    @patch('ga_upload_course_list.views.CourseList._set_course_contents')
    @patch('ga_upload_course_list.views.CourseList._categorize_courses')
    @patch('ga_upload_course_list.views.CourseList._create_templates')
    @patch('ga_upload_course_list.views.CourseList._get_course_card')
    @patch('ga_upload_course_list.views.CourseList._upload_to_store')
    @patch('ga_upload_course_list.views.CourseList._delete_from_store')
    def test_upload_with_template_only_arg(self, dels_m, upls_m, getc_m, crea_m, cate_m, setcc_m, filt_m):
        self.course_list.upload(template_only=True)

        filt_m.assert_any_call(self.course)
        setcc_m.assert_any_call(self.course)
        cate_m.assert_called_once_with([setcc_m(c) for c in self.courses])
        crea_m.assert_called_once_with(cate_m())
        self.assertEquals(getc_m.call_count, 0)
        upls_m.assert_called_once_with(crea_m())
        dels_m.assert_called_once_with(crea_m())

    def test_filter_courses(self):
        ret = self.course_list._filter_courses(self.course)
        self.assertTrue(ret)

    def test_filter_no_category_courses(self):
        ret = self.course_list._filter_courses(self.course_no_category)
        self.assertFalse(ret)

    def test_filter_courses_with_target_category(self):
        ret = self.course_list_with_target._filter_courses(self.course)
        self.assertFalse(ret)

        ret = self.course_list_with_target._filter_courses(self.course_two_categories)
        self.assertTrue(ret)

    def test_filter_courses_passed_enrollment_start(self):
        ret = self.course_list._filter_courses(self.course_not_start)
        self.assertFalse(ret)

    def test_categorize_courses(self):
        ret = self.course_list._categorize_courses(self.courses)
        self.assertEquals(len(ret), 2)
        self.assertEquals(len(ret['cat1']), 4)
        self.assertEquals(len(ret['cat2']), 1)
        self.assertEquals(ret['cat1'][0], self.course_two_categories)
        self.assertEquals(ret['cat1'][1], self.course_terminated)
        self.assertEquals(ret['cat1'][2], self.course)
        self.assertEquals(ret['cat1'][3], self.course_not_start)
        self.assertEquals(ret['cat1'], [self.course_two_categories, self.course_terminated, self.course, self.course_not_start])
        self.assertEquals(ret['cat2'], [self.course_two_categories])
        self.assertEquals(ret, {
            u'cat1': [self.course_two_categories, self.course_terminated, self.course, self.course_not_start],
            u'cat2': [self.course_two_categories],
        })

    def test_set_course_contents_raise_DuplicateDeclaration_course_list_description(self):
        with self.assertRaises(DuplicateDeclaration):
            ret = self.course_list._set_course_contents(CourseFactory.create(course_list_description='dummy'))

    def test_set_course_contents_raise_DuplicateDeclaration_course_card_path(self):
        with self.assertRaises(DuplicateDeclaration):
            ret = self.course_list._set_course_contents(CourseFactory.create(course_card_path='dummy'))

    def test_set_course_contents_raise_DuplicateDeclaration_course_card_data(self):
        with self.assertRaises(DuplicateDeclaration):
            ret = self.course_list._set_course_contents(CourseFactory.create(course_card_data='dummy'))

    def test_set_course_contents_raise_DuplicateDeclaration_course_dict(self):
        with self.assertRaises(DuplicateDeclaration):
            ret = self.course_list._set_course_contents(CourseFactory.create(course_dict='dummy'))

    def test_set_course_contents_raise_CourseCardNotFound(self):
        self.course_list.content_store.find = MagicMock(side_effect=CourseCardNotFound())
        with self.assertRaises(CourseCardNotFound):
            self.course_list._set_course_contents(self.course)

    def test_get_short_description(self):
        self.store.create_item(
            self.user.id, self.course.location.course_key, "about", block_id="short_description",
            fields={"data": "short description!"}
        )

        ret = self.course_list._get_short_description(self.course)
        self.assertEquals(ret, 'short description!')

    def test_get_short_description_null_content(self):
        self.store.create_item(
            self.user.id, self.course.location.course_key, "about", block_id="short_description",
            fields={"data": ""}
        )

        ret = self.course_list._get_short_description(self.course)
        self.assertEquals(ret, '')

    def test_get_short_description_item_not_found(self):
        ret = self.course_list._get_short_description(self.course)
        self.assertEquals(ret, '')

    def test_set_course_contents_get_course_card(self):
        self.course_list.content_store.find.return_value.location.path = self.course.course_image
        course = self.course_list._set_course_contents(self.course)
        ret = self.course_list._get_course_card([course])

        self.course_list.content_store.find.assert_called_with(
            StaticContent.compute_location(
                self.course.location.course_key, self.course.course_image
            )
        )
        self. assertEquals(ret, {
            IMAGE_DIR + 'org/cn1/run.jpg': self.course_list.content_store.find().data
        })

    def test_create_templates(self):
        self.course.course_dict = {"start_date": "2015/11/11"}
        self.course_two_categories.course_dict = {"start_date": "2015/12/12"}
        contents = {
            u'cat1': [self.course, self.course_two_categories],
            u'cat2': [self.course_two_categories],
        }
        ret = self.course_list._create_templates(contents)
        self.assertEquals(ret, {
            u'{}cat1_index.json'.format(CATEGORY_DIR): ANY,
            u'{}cat1_list.json'.format(CATEGORY_DIR): ANY,
            u'{}cat1_archive.json'.format(CATEGORY_DIR): ANY,
            u'{}cat2_index.json'.format(CATEGORY_DIR): ANY,
            u'{}cat2_list.json'.format(CATEGORY_DIR): ANY,
            u'{}cat2_archive.json'.format(CATEGORY_DIR): ANY,
        })

    def test_create_templates_with_target_course(self):
        self.course.course_dict = {"start_date": "2015/11/11"}
        self.course_two_categories.course_dict = {"start_date": "2015/12/12"}
        contents = {
            u'cat1': [self.course, self.course_two_categories],
            u'cat2': [self.course_two_categories],
        }
        ret = self.course_list_with_target._create_templates(contents)
        self.assertEquals(ret, {
            u'{}cat2_index.json'.format(CATEGORY_DIR): ANY,
            u'{}cat2_list.json'.format(CATEGORY_DIR): ANY,
            u'{}cat2_archive.json'.format(CATEGORY_DIR): ANY,
        })

    def test_upload_to_store(self):
        catalog = {
            u'category/cat1.html': "<html><body>cat1</body></html>",
            u'category/cat2.html': "<html><body>cat2</body></html>",
        }
        self.course_list._upload_to_store(catalog)
        self.s3store().save.assert_any_call(u'category/cat1.html', "<html><body>cat1</body></html>")
        self.s3store().save.assert_any_call(u'category/cat2.html', "<html><body>cat2</body></html>")

    def test_delete_from_store(self):
        s3object = s3object2 = MagicMock()
        s3object.name = u'category/cat1.html'
        s3object2.name = u'category/cat3.html'
        self.s3store().list.side_effect = [[s3object], [s3object2]]
        catalog = {
            u'category/cat1.html': "<html><body>cat1</body></html>",
            u'category/cat2.html': "<html><body>cat2</body></html>",
        }
        self.course_list._delete_from_store(catalog)
        self.s3store().list.assert_any_call(prefix=CATEGORY_DIR)
        s3object.delete.assert_called_with()
        self.assertEquals(s3object.delete.call_count, 1)


@override_settings(
    TOP_PAGE_BUCKET_NAME="bucket", AWS_ACCESS_KEY_ID="akey",
    AWS_SECRET_ACCESS_KEY="skey")
class S3StoreTestCase(TestCase):
    def setUp(self):
        self.s3class = create_autospec(S3Connection)
        config = {'return_value': self.s3class}
        patcher1 = patch(
            'ga_upload_course_list.views.S3Store._connect',
            **config)
        self.s3conn = patcher1.start()
        self.addCleanup(patcher1.stop)

        patcher2 = patch('ga_upload_course_list.views.Key')
        self.s3key = patcher2.start()
        self.addCleanup(patcher2.stop)

        self.s3store = S3Store()

    def tearDown(self):
        pass

    @override_settings(
        TOP_PAGE_BUCKET_NAME=None, AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None)
    def test_init_invalid_settings(self):
        with self.assertRaises(InvalidSettings):
            self.s3store = S3Store()

    def test_connect(self):
        conn = self.s3store._connect()
        self.assertEquals(conn, self.s3class)

    def test_list(self):
        object_list = self.s3store.list(prefix=CATEGORY_DIR)

        self.s3conn.assert_called_once_with()
        self.s3class.get_bucket.assert_called_once_with(settings.TOP_PAGE_BUCKET_NAME)
        self.s3class.get_bucket(
            settings.TOP_PAGE_BUCKET_NAME).list.assert_called_once_with(prefix=CATEGORY_DIR)
        self.assertEquals(object_list, self.s3class.get_bucket(
            settings.TOP_PAGE_BUCKET_NAME).list(prefix=CATEGORY_DIR))

    def test_save(self):
        self.s3store.save(objectpath="path", data="data")
        self.s3conn.assert_called_once_with()
        self.s3class.get_bucket.assert_called_once_with(settings.TOP_PAGE_BUCKET_NAME)
        self.s3key.assert_called_once_with(self.s3class.get_bucket(settings.TOP_PAGE_BUCKET_NAME))
        self.s3key().set_contents_from_string.assert_called_once_with("data")
        self.s3key().close.assert_called_once_with()

    def test_save_raise_S3ResponseError(self):
        expected_error = S3ResponseError(status="dummy", reason="reason")
        self.s3class.get_bucket.side_effect = expected_error
        s3store = S3Store()
        with self.assertRaises(S3ResponseError) as cm:
            s3store.save(objectpath="path", data="data")
        self.assertEquals(expected_error.status, cm.exception.status)
        self.assertEquals(expected_error.reason, cm.exception.reason)

    def test_save_raise_S3ResponseError_and_404(self):
        expected_error = S3ResponseError(status=404, reason="reason")
        self.s3class.get_bucket.side_effect = expected_error
        s3store = S3Store()
        s3store.save(objectpath="path", data="data")

        self.s3conn.assert_any_call()
        self.s3class.get_bucket.assert_called_once_with(settings.TOP_PAGE_BUCKET_NAME)
        self.s3class.create_bucket.assert_called_once_with(
            settings.TOP_PAGE_BUCKET_NAME, location=Location.APNortheast)
        self.s3key.assert_called_once_with(self.s3class.create_bucket(
            settings.TOP_PAGE_BUCKET_NAME, Location.APNortheast))
        self.s3key().set_contents_from_string.assert_called_once_with("data")
        self.s3key().close.assert_called_once_with()
