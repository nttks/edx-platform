;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                'click #aggregate_g1528': 'clickAggregateG1528'
            },
            clickAggregateG1528: function (event) {
                this.post(event, 'aggregate_g1528');
            }
        });
    });

})(define || RequireJS.define);

