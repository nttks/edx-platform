define(['js/ga_operation/ga_operation_router'],
    function (GaOperationRouter) {
        var gaOperationRouter = GaOperationRouter;
        describe('GaOperationRouter', function () {
            it('has a router route', function () {
                expect(gaOperationRouter.routes['']).toEqual('deleteCourse');
                expect(gaOperationRouter.routes['delete_course']).toEqual('deleteCourse');
                expect(gaOperationRouter.routes['delete_library']).toEqual('deleteLibrary');
            });
            it('deleteCourse is not error', function () {
                spyOn(gaOperationRouter, '_render');
                gaOperationRouter.deleteCourse();
                expect(gaOperationRouter._render).toHaveBeenCalled();
            });
            it('deleteLibrary is not error', function () {
                spyOn(gaOperationRouter, '_render');
                gaOperationRouter.deleteLibrary();
                expect(gaOperationRouter._render).toHaveBeenCalled();
            });
        });
    });
