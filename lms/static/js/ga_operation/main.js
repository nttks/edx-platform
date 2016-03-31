RequireJS.require([
    'backbone',
    'js/ga_operation/ga_operation_app',
    'js/ga_operation/ga_operation_router',
    'js/ga_operation/views/ga_base',
    'js/ga_operation/views/move_videos'
], function (Backbone, GaOperationApp, GaOperationRouter, GaBaseView, MoveVideos) {
    'use strict';

    var app = new GaOperationApp(
        GaOperationRouter,
        GaBaseView,
        MoveVideos
    );
    Backbone.history.start();
});
