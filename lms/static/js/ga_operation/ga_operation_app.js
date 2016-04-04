;(function (define) {

    define(['backbone'], function(Backbone) {
        'use strict';

        return function (GaOperationRouter, GaBaseView, MoveVideos, CreateCerts, CreateCertsMeeting, PublishCerts) {
            var ga_operation_router = new GaOperationRouter();
            var ga_base_view = new GaBaseView();
            var move_videos = new MoveVideos();
            var create_certs = new CreateCerts();
            var create_certs_meeting = new CreateCertsMeeting();
            var publish_certs = new PublishCerts();

        };

    });

})(define || RequireJS.define);
