# -*- coding: utf-8 -*-
from django import forms
from django.conf import settings

from opaque_keys.edx.keys import CourseKey

from openedx.core.djangoapps.ga_operation.utils import course_filename, handle_uploaded_received_file_to_s3
from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationBaseForm


class ConfirmCertsTemplateForm(GaOperationBaseForm):
    pass


class UploadCertsTemplateForm(GaOperationBaseForm):
    cert_pdf_tmpl = forms.FileField(required=False)
    cert_pdf_meeting_tmpl = forms.FileField(required=False)

    def clean(self):
        cleaned_data = super(UploadCertsTemplateForm, self).clean()

        if not cleaned_data.get('cert_pdf_tmpl') and not cleaned_data.get('cert_pdf_meeting_tmpl'):
            self._errors['cert_pdf_tmpl_error'] = u'通常テンプレートと対面学習テンプレートのどちらか一方または両方を選択してください。'

        return cleaned_data

    def upload(self):
        course_key = CourseKey.from_string(self.cleaned_data.get('course_id'))
        cert_pdf_tmpl = self.cleaned_data.get('cert_pdf_tmpl')
        cert_pdf_meeting_tmpl = self.cleaned_data.get('cert_pdf_meeting_tmpl')

        if cert_pdf_tmpl:
            handle_uploaded_received_file_to_s3(
                cert_pdf_tmpl,
                '{}.pdf'.format(course_filename(course_key)),
                settings.PDFGEN_BASE_BUCKET_NAME
            )

        if cert_pdf_meeting_tmpl:
            handle_uploaded_received_file_to_s3(
                cert_pdf_meeting_tmpl,
                'verified-{}.pdf'.format(course_filename(course_key)),
                settings.PDFGEN_BASE_BUCKET_NAME
            )
