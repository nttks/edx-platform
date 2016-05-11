# -*- coding: utf-8 -*-
from django import forms

from ga_operation.forms.ga_operation_base_form import GaOperationBaseForm


class PastGraduatesInfoForm(GaOperationBaseForm):
    def clean_course_id(self):
        return_val = self.cleaned_data.get('course_id')
        # In case of lacking run parameter in course_id, that permit it.
        # Because, use fuzzy search from SQL.
        for suffix in ['', '+XXXX_XX']:
            self.cleaned_data['course_id'] += suffix
            try:
                super(PastGraduatesInfoForm, self).clean_course_id()
            except forms.ValidationError:
                if len(suffix):
                    raise forms.ValidationError(u"講座IDの書式が不正です。")
                else:
                    continue
            else:
                break
        return return_val
