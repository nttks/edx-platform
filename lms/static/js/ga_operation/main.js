RequireJS.require([
    'backbone',
    'js/ga_operation/ga_operation_app',
    'js/ga_operation/ga_operation_router',
    'js/ga_operation/views/ga_base',
    'js/ga_operation/views/move_videos',
    'js/ga_operation/views/create_certs',
    'js/ga_operation/views/create_certs_meeting',
    'js/ga_operation/views/publish_certs'
], function (
    Backbone,
    GaOperationApp,
    GaOperationRouter,
    GaBaseView,
    MoveVideos,
    CreateCerts,
    CreateCertsMeeting,
    PublishCerts
) {
    'use strict';

    var app = new GaOperationApp(
        GaOperationRouter,
        GaBaseView,
        MoveVideos,
        CreateCerts,
        CreateCertsMeeting,
        PublishCerts
    );
    Backbone.history.start();
});
