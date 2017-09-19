define(['domReady', 'jquery', 'underscore', 'js/utils/cancel_on_escape', 'js/views/utils/create_course_utils',
    'js/views/utils/create_library_utils', 'common/js/components/utils/view_utils', 'js/index'],
    function (domReady, $, _, CancelOnEscape, CreateCourseUtilsFactory, CreateLibraryUtilsFactory, ViewUtils, CreateLibrary) {
        describe('CreateLibrary', function () {
            it('Change course_key is not error', function () {
                var createLibrary = CreateLibrary;
                createLibrary.course_key_setter(undefined);
                expect(createLibrary.course_key).toEqual(undefined);
            });
        });
    }
);
