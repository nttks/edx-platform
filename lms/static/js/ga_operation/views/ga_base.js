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
                        if (_.isFunction(value.replace)) {
                            $('#' + key).html(value.replace(/\r?\n/g, '<br>'));
                        } else {
                            $('#' + key).text(value);
                        }
                    });
                }

                event.preventDefault();

                if (!window.FormData) {
                    alert('Sorry, this browser does not support!\nPlease use modern browser.');
                } else {
                    var form = $('#input_form').get(0);
                    var formData = new FormData(form);
                    $.ajax({
                        url: 'ga_operation/api/' + url,
                        type: 'POST',
                        data: formData,
                        contentType: false,
                        processData: false,
                        beforeSend: function () {
                            $('.error').text('');
                            $('#right_content_response').text('');
                            $('#indicator').show();
                            $('.button').hide();
                        }
                    }).done(function (response) {
                        _setMsg(response);
                    }).fail(function (response) {
                        _setMsg(response.responseText);
                    }).always(function () {
                        $('#indicator').hide();
                        $('.button').show();
                    });
                }
            },
            downloadFileWithCourseId: function (url) {
                event.preventDefault();
                var course_id = $('input[name="course_id"]').val();
                window.open('/ga_operation/api/' + url + '/?course_id=' + encodeURIComponent(course_id), '_blank');
            }
        });
    });

})(define || RequireJS.define);
