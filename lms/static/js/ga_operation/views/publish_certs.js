;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                'click #publish_certs': 'clickPublishCerts'
            },
            clickPublishCerts: function (event) {
                this.post(event, 'publish_certs');
            }
        });
    });

})(define || RequireJS.define);
