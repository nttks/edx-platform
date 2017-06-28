function initGaDiagnosisPullDown(list) {
    _.each(list, function (children) {
        if (children.find("option:selected").val() === "") {
            children.attr("disabled", "disabled");
        }
    });
}

function changeGaDiagnosisPullDown(parent, $children, original) {
    "use strict";
    var val1 = $(parent).val();
    $children.html(original).find("option").each(function () {
        var val2 = $(this).data("str");
        if (_.isNumber(val2)) {
            val2 = ("00" + val2).slice(-2);
        }
        if (val1 !== val2) {
            $(this).not(":first-child").remove();
        }
    });

    if ($(parent).val() === "") {
        $children.attr("disabled", "disabled");
    } else {
        $children.removeAttr("disabled");
    }
}
