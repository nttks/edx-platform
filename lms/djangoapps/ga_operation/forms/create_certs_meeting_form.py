from django import forms

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationCertsBaseForm, GaOperationEmailField


class CreateCertsMeetingForm(GaOperationCertsBaseForm):
    # student_ids is required when creating the meeting certificate
    student_ids = forms.CharField(required=True)
    email = GaOperationEmailField(required=True)
