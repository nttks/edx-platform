;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #all_users_info": "clickAllUsersInfo"
            },
            clickAllUsersInfo: function (event) {
                this.post(event, 'all_users_info');
            }
        });
    });

})(define || RequireJS.define);
