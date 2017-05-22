window.require([
    'backbone',
    'js/ga_operation/ga_operation_app',
    'js/ga_operation/ga_operation_router',
    'js/ga_operation/views/ga_base',
    'js/ga_operation/views/delete_course'
], function (Backbone,
             GaOperationApp,
             GaOperationRouter,
             GaBaseView,
             DeleteCourse) {
    'use strict';

    new GaOperationApp(
        GaOperationRouter,
        GaBaseView,
        DeleteCourse
    );
    Backbone.history.start({pushState: false});
});
