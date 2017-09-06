;(function (define) {

    define(['backbone'], function(Backbone) {
        'use strict';

        return function (GaOperationRouter, GaBaseView, MoveVideos, UploadCertsTemplate, CreateCerts, CreateCertsMeeting, PublishCerts,
                         MutualGradingReport, DiscussionData, PastGraduatesInfo, LastLoginInfo, AggregateG1528,
                         AllUsersInfo, CreateCertsStatus, EnrollmentStatus, DisabledAccountInfo) {
            var gaOperationRouter = new GaOperationRouter();
            var gabaseView = new GaBaseView();
            var moveVideos = new MoveVideos();
            var createCerts = new CreateCerts();
            var createCerts_meeting = new CreateCertsMeeting();
            var publishCerts = new PublishCerts();
            var mutualGrading_report = new MutualGradingReport();
            var discussionData = new DiscussionData();
            var pastGraduatesInfo = new PastGraduatesInfo();
            var lastLoginInfo = new LastLoginInfo();
            var aggregateG1528 = new AggregateG1528();
            var allUsersInfo = new AllUsersInfo();
            var createCertsStatus = new CreateCertsStatus();
            var enrollmentStatus = new EnrollmentStatus();
            var disabledAccountInfo = new DisabledAccountInfo();
            new UploadCertsTemplate();
        };

    });

})(define || RequireJS.define);
