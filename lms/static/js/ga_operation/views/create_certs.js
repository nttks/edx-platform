;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                'click #create_certs': 'clickCreateCerts'
            },
            clickCreateCerts: function (event) {
                this.post(event, 'create_certs');
            }
        });
    });

})(define || RequireJS.define);
