;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #enrollment_status": "clickEnrollmentStatus"
            },
            clickEnrollmentStatus: function (event) {
                this.post(event, 'enrollment_status');
            }
        });
    });

})(define || RequireJS.define);
