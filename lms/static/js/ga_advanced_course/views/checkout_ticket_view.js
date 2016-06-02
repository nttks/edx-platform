/**
 * View for the advanced course checkout ticket page
 */
var edx = edx || {};

(function($, _, Backbone){
    'use strict';

    edx.ga_advanced_course = edx.ga_advanced_course || {};

    edx.ga_advanced_course.AdvancedF2FCourseCheckoutView = Backbone.View.extend({

        getOrderId: function() {
            return $('#order-id').val();
        },

        checkout: function() {
            var postData = {
                'order_id': this.getOrderId()
            };

            // Create the order for the amount
            $.ajax({
                url: '/advanced_course/checkout/',
                type: 'POST',
                headers: {
                    'X-CSRFToken': $.cookie('csrftoken')
                },
                data: postData,
                context: this,
                success: this.handleCreateOrderResponse,
            });
        },

        handleCreateOrderResponse: function( paymentData ) {
            var form = $('#payment-processor-form');

            $('input', form).remove();

            form.attr('action', paymentData.payment_page_url);
            form.attr('method', 'POST');

            _.each(paymentData.payment_form_data, function(value, key) {
                $('<input>').attr({
                    type: 'hidden',
                    name: key,
                    value: value
                }).appendTo(form);
            });

            form.submit();
        },
    });

    new edx.ga_advanced_course.AdvancedF2FCourseCheckoutView().checkout();

})(jQuery, _, Backbone);
