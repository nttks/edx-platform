from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationBaseForm, GaOperationEmailField


class DeleteLibraryForm(GaOperationBaseForm):
    email = GaOperationEmailField(required=True)
