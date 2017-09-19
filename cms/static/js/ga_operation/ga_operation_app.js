;(function (define) {
    'use strict';
    define(['backbone'], function() {

        return function (GaOperationRouter, GaBaseView, DeleteCourse, DeleteLibrary) {
            new DeleteCourse();
            new DeleteLibrary();
        };

    });

})(define || RequireJS.define);
