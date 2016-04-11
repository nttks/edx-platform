;(function (define) {

    define(['backbone'], function(Backbone) {
        'use strict';

        return function (GaOperationRouter, GaBaseView, MoveVideos) {

            var ga_operation_router = new GaOperationRouter();
            var ga_base_view = new GaBaseView();
            var move_videos = new MoveVideos();
        };

    });

})(define || RequireJS.define);
