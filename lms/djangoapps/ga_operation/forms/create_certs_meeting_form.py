from django import forms

from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationCertsBaseForm, GaOperationEmailField, FIELD_NOT_INPUT, INVALID_EMAIL


class CreateCertsMeetingForm(GaOperationCertsBaseForm):
    # student_ids is required when creating the meeting certificate
    student_ids = forms.CharField(required=True, error_messages={'required': FIELD_NOT_INPUT})
    email = GaOperationEmailField(required=True, error_messages={'required': FIELD_NOT_INPUT, 'invalid': INVALID_EMAIL})
