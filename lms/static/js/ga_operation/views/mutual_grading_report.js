;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #mutual_grading_report": "clickMutualGradingReport"
            },
            clickMutualGradingReport: function (event) {
                this.post(event, 'mutual_grading_report');
            }
        });
    });

})(define || RequireJS.define);
