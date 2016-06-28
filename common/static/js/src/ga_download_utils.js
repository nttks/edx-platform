(function($) {
    window.downloadFileUsingPost = function (url) {
        // Download file to POST endpoint
        var $form = $('<form></form>').attr('action', url).attr('method', 'POST');
        $form.append(
            $('<input>').attr('type', 'hidden')
                        .attr('name', 'csrfmiddlewaretoken')
                        .attr('value', $.cookie('csrftoken'))
        );
        $form.appendTo('body').submit().remove();
    };
})(jQuery);
