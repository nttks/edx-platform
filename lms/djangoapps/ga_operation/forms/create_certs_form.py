from ga_operation.forms.ga_operation_base_form import GaOperationCertsBaseForm, GaOperationEmailField


class CreateCertsForm(GaOperationCertsBaseForm):
    email = GaOperationEmailField(required=True)
