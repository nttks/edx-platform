# -*- coding: utf-8 -*-
import re

from django import forms
from django.conf import settings

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

FIELD_NOT_INPUT = u'このフィールドは必須です。'
INVALID_EMAIL = u'有効なメールアドレスを入力してください。'


class GaOperationBaseForm(forms.Form):
    course_id = forms.CharField(required=True, error_messages={'required': FIELD_NOT_INPUT})

    def clean_course_id(self):
        val = self.cleaned_data.get('course_id')
        try:
            CourseKey.from_string(val)
        except InvalidKeyError:
            raise forms.ValidationError(u"講座IDの書式が不正です。")
        return val


class GaOperationCertsBaseForm(GaOperationBaseForm):
    student_ids = forms.CharField(required=False)

    def clean_student_ids(self):
        from instructor.views.api import _split_input_list
        return _split_input_list(self.cleaned_data.get('student_ids'))


class GaOperationEmailField(forms.EmailField):
    def clean(self, value):
        super(GaOperationEmailField, self).clean(value)
        # permit valid domains only.
        for domain in settings.GA_OPERATION_VALID_DOMAINS_LIST:
            if re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@{}$'.format(domain), value):
                return value
        raise forms.ValidationError(u"このドメインのEメールは使用できません。")


class GaOperationDeleteCourseForm(forms.Form):
    course_id = forms.CharField(required=True, error_messages={'required': FIELD_NOT_INPUT})

    def clean_course_id(self):
        val = self.cleaned_data.get('course_id')
        if not re.match(settings.GA_OPERATION_COURSE_ID_PATTERN, val):
            raise forms.ValidationError(u"講座IDの書式が不正です。")
        return val


class GaOperationDeleteLibraryForm(forms.Form):
    library_id = forms.CharField(required=True, error_messages={'required': FIELD_NOT_INPUT})

    def clean_library_id(self):
        val = self.cleaned_data.get('library_id')
        if not re.match(settings.GA_OPERATION_LIBRARY_KEY_PATTERN, val):
            raise forms.ValidationError(u"ライブラリIDの書式が不正です。")
        return val
