# -*- coding: utf-8 -*-
from django import forms

from ga_operation.forms.ga_operation_base_form import GaOperationBaseForm, GaOperationEmailField


class CreateCertsForm(GaOperationBaseForm):
    cert_pdf_tmpl = forms.FileField(required=True)
    email = GaOperationEmailField(required=True)
