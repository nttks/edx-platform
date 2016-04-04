# -*- coding: utf-8 -*-
from django import forms

from ga_operation.forms.ga_operation_base_form import GaOperationBaseForm


class CreateCertsMeetingForm(GaOperationBaseForm):
    cert_pdf_tmpl = forms.FileField(required=True)
    cert_pdf_meeting_tmpl = forms.FileField(required=True)
    cert_lists = forms.FileField(required=True)
    email = forms.CharField(required=True)

