RequireJS.require([
    'backbone',
    'js/ga_operation/ga_operation_app',
    'js/ga_operation/ga_operation_router',
    'js/ga_operation/views/ga_base',
    'js/ga_operation/views/move_videos',
    'js/ga_operation/views/create_certs',
    'js/ga_operation/views/create_certs_meeting',
    'js/ga_operation/views/publish_certs',
    'js/ga_operation/views/mutual_grading_report',
    'js/ga_operation/views/discussion_data',
    'js/ga_operation/views/past_graduates_info',
    'js/ga_operation/views/last_login_info',
    'js/ga_operation/views/aggregate_g1528'
], function (
    Backbone,
    GaOperationApp,
    GaOperationRouter,
    GaBaseView,
    MoveVideos,
    CreateCerts,
    CreateCertsMeeting,
    PublishCerts,
    MutualGradingReport,
    DiscussionData,
    PastGraduatesInfo,
    LastLoginInfo,
    AggregateG1528
) {
    'use strict';

    var app = new GaOperationApp(
        GaOperationRouter,
        GaBaseView,
        MoveVideos,
        CreateCerts,
        CreateCertsMeeting,
        PublishCerts,
        MutualGradingReport,
        DiscussionData,
        PastGraduatesInfo,
        LastLoginInfo,
        AggregateG1528
    );
    Backbone.history.start();
});
