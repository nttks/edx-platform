;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #discussion_data": "clickDiscussionData",
                "click #discussion_data_download": "clickDiscussionDataDownload"
            },
            clickDiscussionData: function (event) {
                this.post(event, 'discussion_data');
            },
            clickDiscussionDataDownload: function (event) {
                this.downloadFileWithCourseId('discussion_data_download', event);
            }
        });
    });

})(define || RequireJS.define);
