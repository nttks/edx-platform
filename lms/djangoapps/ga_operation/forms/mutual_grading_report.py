# -*- coding: utf-8 -*-
from django import forms

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationBaseForm, FIELD_NOT_INPUT, INVALID_EMAIL


class MutualGradingReportForm(GaOperationBaseForm):
    email = forms.EmailField(required=True, error_messages={'required': FIELD_NOT_INPUT, 'invalid': INVALID_EMAIL})
