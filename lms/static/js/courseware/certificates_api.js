$(document).ready(function() {
    'use strict';

    $(".generate_certs").click(function(e){
        e.preventDefault();
        var post_url = $(".generate_certs").data("endpoint");
        $(".generate_certs").attr("disabled", true).addClass('is-disabled').attr('aria-disabled', true);
        $.ajax({
            type: "POST",
            url: post_url,
            dataType: 'text',
            success: function () {
                $(".auto-cert-message .msg-content .title").text(gettext("We're working on it..."));
                $(".auto-cert-message .msg-content .copy").text(gettext("We're creating your certificate. You can keep working in your courses and a link to it will appear here and on your Dashboard when it is ready."));
                $(".msg-actions").empty();
                setTimeout(function() {
                    location.reload();
                }, 30 * 1000);
            },
            error: function(jqXHR, textStatus, errorThrown) {
                location.reload();
            }
        });
    });
});
