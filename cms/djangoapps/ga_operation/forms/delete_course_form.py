from openedx.core.djangoapps.ga_operation.ga_operation_base_form import GaOperationEmailField, GaOperationDeleteCourseForm, FIELD_NOT_INPUT


class DeleteCourseForm(GaOperationDeleteCourseForm):
    email = GaOperationEmailField(required=True, error_messages={'required': FIELD_NOT_INPUT})
