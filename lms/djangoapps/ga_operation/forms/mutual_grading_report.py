# -*- coding: utf-8 -*-
from django import forms

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationBaseForm


class MutualGradingReportForm(GaOperationBaseForm):
    email = forms.EmailField(required=True)
