# -*- coding: utf-8 -*-
from django import forms

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationEmailField


class AggregateG1528Form(forms.Form):
    course_lists_file = forms.FileField(required=True)
    email = GaOperationEmailField(required=True)
