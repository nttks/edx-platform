define(['jquery', 'js/factories/index', 'js/index'],
    function ($, FactoriesIndex, CreateLibrary) {
        describe('FactoriesIndex', function () {
            it('CreateLibrary.course_key_setter is ones colled', function () {
                spyOn(CreateLibrary, 'course_key_setter');
                var factoriesIndex = new FactoriesIndex(undefined)
                expect(CreateLibrary.course_key_setter).toHaveBeenCalled();
            });
        });
    }
);
