/**
 * Provides utilities for validating libraries during creation.
 */
define(["jquery", "gettext", "common/js/components/utils/view_utils", "js/views/utils/create_utils_base"],
    function ($, gettext, ViewUtils, CreateUtilsFactory) {
        "use strict";
        return function (selectors, classes) {
            var keyLengthViolationMessage = gettext("The length of library code fields cannot be more than <%=limit%> characters.");
            var keyFieldSelectors = [selectors.number];
            var nonEmptyCheckFieldSelectors = [selectors.name, selectors.org, selectors.number];
            // default length is 65. 58 is subtracted Suffix[___0000].
            var MAX_SUM_KEY_LENGTH = 58;

            var orgObjVal = $(selectors.org).val();
            var orgLength = 0;
            if (orgObjVal) {
              orgLength = orgObjVal.length;
            }
            CreateUtilsFactory.call(this, selectors, classes, keyLengthViolationMessage, keyFieldSelectors, nonEmptyCheckFieldSelectors, MAX_SUM_KEY_LENGTH - orgLength);

            this.create = function (libraryInfo, course_key, errorHandler) {
                $.postJSON(
                    '/course/' + course_key + '/library/',
                    libraryInfo,
                    course_key
                ).done(function (data) {
                    ViewUtils.redirect(data.url);
                }).fail(function(jqXHR, textStatus, errorThrown) {
                    var reason = errorThrown;
                    if (jqXHR.responseText) {
                        try {
                            var detailedReason = $.parseJSON(jqXHR.responseText).ErrMsg;
                            if (detailedReason) {
                                reason = detailedReason;
                            }
                        } catch (e) {}
                    }
                    errorHandler(reason);
                });
            }
        };
    });
