;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                "click #past_graduates_info": "clickPastGraduatesInfo"
            },
            clickPastGraduatesInfo: function (event) {
                this.downloadFileWithCourseId('past_graduates_info', event);
            }
        });
    });

})(define || RequireJS.define);
