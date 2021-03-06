# -*- coding: utf-8 -*-
from django import forms

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationEmailField, FIELD_NOT_INPUT, INVALID_EMAIL


class AggregateG1528Form(forms.Form):
    course_lists_file = forms.FileField(required=True, error_messages={'required': FIELD_NOT_INPUT})
    email = GaOperationEmailField(required=True, error_messages={'required': FIELD_NOT_INPUT, 'invalid': INVALID_EMAIL})
