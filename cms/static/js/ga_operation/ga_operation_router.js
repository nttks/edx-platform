;(function (define) {
    'use strict';
    define(['backbone', 'underscore'], function (Backbone, _) {

        var Router = Backbone.Router.extend({
            routes: {
                "": "deleteCourse",
                "delete_course": "deleteCourse",
                "delete_library": "deleteLibrary"
            },
            deleteCourse: function () {
                this._render("delete_course_tmpl");
            },
            deleteLibrary: function () {
                this._render("delete_library_tmpl");
            },
            _render: function (id_name) {
                $('#right_content_response').text('');
                var template = $('#' + id_name).text();
                $('#right_content_main').html(_.template(template));
            }
        });
        return new Router();

    });

})(define || RequireJS.define);
