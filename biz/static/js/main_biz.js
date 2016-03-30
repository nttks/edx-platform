$(function () {
    // Set up leanModal for biz
    $('a[rel="biz-modal"]').leanModal({
        closeButton: '.biz-modal-close'
    });

    // Prevent double click
    $('form.preventDoubleClick').submit(function () {
        $('button[type="submit"], input[type="submit"]', this).attr('disabled', true);
    });
});
