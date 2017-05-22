from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationCertsBaseForm, GaOperationEmailField


class CreateCertsForm(GaOperationCertsBaseForm):
    email = GaOperationEmailField(required=True)
