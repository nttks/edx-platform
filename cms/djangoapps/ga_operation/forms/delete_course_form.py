from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationBaseForm, GaOperationEmailField


class DeleteCourseForm(GaOperationBaseForm):
    email = GaOperationEmailField(required=True)
