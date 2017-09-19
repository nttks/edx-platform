define(['js/ga_operation/ga_operation_app', 'js/ga_operation/ga_operation_router',
        'js/ga_operation/views/ga_base', 'js/ga_operation/views/delete_course',
        'js/ga_operation/views/delete_library'],
    function (GaOperationApp, GaOperationRouter, GaBaseView, DeleteCourse, DeleteLibrary) {

        describe('GaOperationApp', function () {
            it('gaOperationApp is not error', function () {
                expect(function () {
                    GaOperationApp(GaOperationRouter, GaBaseView, DeleteCourse, DeleteLibrary)
                }).not.toThrow();
            });
        });
    });
