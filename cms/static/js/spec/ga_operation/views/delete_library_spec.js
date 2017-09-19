define(["js/ga_operation/views/delete_library"],
    function (DeleteLibrary) {

        describe("DeleteLibrary", function () {
            it('return window.alert if window.confirm is false', function () {
                var deleteLibrary = new DeleteLibrary();
                var event = {};
                spyOn(window, 'confirm').andReturn(false);
                spyOn(window, 'alert');
                deleteLibrary.clickDeleteLibrary(event);
                expect(window.alert).toHaveBeenCalled();
            });
        });
    });
