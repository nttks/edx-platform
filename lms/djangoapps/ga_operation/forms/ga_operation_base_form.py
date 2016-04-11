# -*- coding: utf-8 -*-
from django import forms

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey


class GaOperationBaseForm(forms.Form):
    course_id = forms.CharField(required=True)

    def clean_course_id(self):
        val = self.cleaned_data.get('course_id')
        try:
            CourseKey.from_string(val)
        except InvalidKeyError:
            raise forms.ValidationError(u"講座IDの書式が不正です。")
        return val
