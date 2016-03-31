;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                'click #move_videos': 'clickMoveVideos'
            },
            clickMoveVideos: function (event) {
                this.post(event, 'move_videos');
            }
        });
    });

})(define || RequireJS.define);
