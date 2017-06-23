$(function () {
    // Set up leanModal for biz
    $('a[rel="biz-modal"]').leanModal({
        closeButton: '.biz-modal-close'
    });

    // Prevent double click
    $('form.prevent-double-click').submit(function () {
        $('button[type="submit"], input[type="submit"]', this).attr('disabled', true);
    });
});

function renderTime(record, index, column_index) {
    var value = record[this.columns[column_index].field] || 0;
    var m = Math.floor(value / 60) + Math.ceil(value % 60 / 60);
    return (Math.floor(m / 60)) + ":" + (("0" + m % 60).slice(-2));
}

function renderPercent(record, index, column_index) {
    var value = record[this.columns[column_index].field];
    // Note: '―'(U+2015) means 'Not Attempted' (#1816)
    if (value === '―') {
        return value;
    }
    var pow = Math.pow(10 , 1) ;
    return (Math.round(parseFloat(value) * 100 * pow) / pow).toFixed(1) + '%';
}
