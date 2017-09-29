# -*- coding: utf-8 -*-
from datetime import date

from django import forms
from django.forms.util import ErrorList

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import (GaOperationEmailField,
                                                                         FIELD_NOT_INPUT, INVALID_EMAIL)


class SearchByEmailAndPeriodDateForm(forms.Form):
    start_date = forms.DateField(input_formats=['%Y%m%d'], required=False)
    end_date = forms.DateField(input_formats=['%Y%m%d'], required=False)
    email = GaOperationEmailField(required=True,
                                  error_messages={'required': FIELD_NOT_INPUT, 'invalid': INVALID_EMAIL})

    def clean_start_date(self):
        val = self.cleaned_data['start_date']

        if not val:
            return date(2014, 1, 9)

        if val < date(2014, 1, 9):
            raise forms.ValidationError(u"集計開始日は20140109以降の日付を入力してください。")
        return val

    def clean_end_date(self):
        val = self.cleaned_data['end_date']

        if not val:
            return date.today()

        if val > date.today():
            raise forms.ValidationError(u"集計終了日は本日以前の日付を入力してください。")
        return val

    def clean(self):
        """
        Checks multi fields correlation

        :return: clean data
        """
        cleaned_data = self.cleaned_data

        # check inputs
        start_date = cleaned_data['start_date']
        end_date = cleaned_data['end_date']

        if start_date > end_date:
            self.errors["end_date"] = ErrorList([u"終了日は開始日以降の日付を入力してください。"])

        return cleaned_data
