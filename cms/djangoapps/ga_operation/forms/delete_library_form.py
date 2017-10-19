from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationEmailField, GaOperationDeleteLibraryForm, FIELD_NOT_INPUT


class DeleteLibraryForm(GaOperationDeleteLibraryForm):
    email = GaOperationEmailField(required=True, error_messages={'required': FIELD_NOT_INPUT})
