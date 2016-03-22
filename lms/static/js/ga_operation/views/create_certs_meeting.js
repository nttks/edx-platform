;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                'click #create_certs_meeting': 'clickCreateCertsMeeting'
            },
            clickCreateCertsMeeting: function (event) {
                this.post(event, 'create_certs_meeting');
            }
        });
    });

})(define || RequireJS.define);
