;(function (define) {

    define(['jquery', 'underscore', 'backbone'], function ($, _, Backbone) {
        'use strict';

        return Backbone.View.extend({
            el: '#right_content_main',
            post: function (event, url) {
                function _setMsg(responseText) {
                    var response_dict;
                    if (_.isString(responseText)) {
                        response_dict = JSON.parse(responseText);
                    } else {
                        response_dict = responseText;
                    }
                    _.each(response_dict, function (value, key) {
                        $('#' + key).text(value)
                    });
                }

                event.preventDefault();

                $.ajax({
                    url: 'ga_operation/api/' + url,
                    type: 'POST',
                    data: $('#input_form').serialize(),
                    beforeSend: function () {
                        $('#right_content_response').text('');
                        $('#indicator').show();
                        $('.button').hide();
                    }
                }).success(function (response) {
                    _setMsg(response);
                }).error(function (response) {
                    _setMsg(response.responseText);
                }).always(function () {
                    $('#indicator').hide();
                    $('.button').show();
                });
            }
        });
    });

})(define || RequireJS.define);
