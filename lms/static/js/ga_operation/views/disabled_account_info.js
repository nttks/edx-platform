;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #disabled_account_info": "clickDisabledAccountInfo"
            },
            clickDisabledAccountInfo: function (event) {
                this.post(event, 'disabled_account_info');
            }
        });
    });

})(define || RequireJS.define);
