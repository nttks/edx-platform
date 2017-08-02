from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationCertsBaseForm, GaOperationEmailField, FIELD_NOT_INPUT, INVALID_EMAIL


class CreateCertsForm(GaOperationCertsBaseForm):
    email = GaOperationEmailField(required=True, error_messages={'required': FIELD_NOT_INPUT, 'invalid': INVALID_EMAIL})
