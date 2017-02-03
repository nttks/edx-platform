;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #last_login_info": "clickLastLoginInfo"
            },
            clickLastLoginInfo: function (event) {
                this.downloadFileWithCourseId('last_login_info', event);
            }
        });
    });

})(define || RequireJS.define);
