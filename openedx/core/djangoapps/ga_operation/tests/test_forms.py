# -*- coding: utf-8 -*-
import ddt

from django.forms import ValidationError
from django.test import TestCase
from django.test.utils import override_settings

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import (
    GaOperationBaseForm, GaOperationCertsBaseForm, GaOperationEmailField
)


@ddt.ddt
class GaOperationBaseFormTest(TestCase):

    @ddt.data(
        'course-v1:org+course+run',
        'org/course/run',
    )
    def test_clean_course_id_valid(self, course_id):
        form = GaOperationBaseForm({'course_id': course_id})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['course_id'], course_id)

    @ddt.data(
        'course-v1:org+course/run',
        'org/course+run',
    )
    def test_clean_course_id_invalid(self, course_id):
        form = GaOperationBaseForm({'course_id': course_id})
        self.assertFalse(form.is_valid())


@ddt.ddt
class GaOperationCertsBaseFormTest(TestCase):

    @ddt.data(
        ('', []),
        (None, []),
        ('user1', ['user1']),
        ('user1@example.com,user2', ['user1@example.com', 'user2']),
        ('user1, user2\nuser3\r\n user4,\n', ['user1', 'user2', 'user3', 'user4'])
    )
    @ddt.unpack
    def test_clean_student_ids(self, student_ids, expected):
        form = GaOperationCertsBaseForm({'course_id': 'course-v1:org+course+run', 'student_ids': student_ids})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['student_ids'], expected)


@ddt.ddt
@override_settings(GA_OPERATION_VALID_DOMAINS_LIST=['test1.com', 'test2.com'])
class GaOperationEmailFieldTest(TestCase):

    @ddt.data(
        'a.z@test1.com',
        '0.9@test1.com',
        '_._@test2.com',
        '-.-@test2.com',
    )
    def test_clean_valid(self, email):
        self.assertEqual(GaOperationEmailField().clean(email), email)

    @ddt.data(
        'te.st@test1.comX',
        'te＊st@test3.com',
    )
    def test_clean_invalid(self, email):
        with self.assertRaises(ValidationError) as e:
            GaOperationEmailField().clean(email)
        self.assertEqual(e.exception.message, u"このドメインのEメールは使用できません。")
