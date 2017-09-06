;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #create_certs_status": "clickCreateCertsStatus"
            },
            clickCreateCertsStatus: function (event) {
                this.post(event, 'create_certs_status');
            }
        });
    });

})(define || RequireJS.define);
