;(function (define) {

    define(['backbone'], function (Backbone) {
        'use strict';

        return Backbone.Router.extend({
            routes: {
                '': 'index',
                'create_certs': 'create_certs',
                'move_videos': 'moveVideos'
            },
            index: function() {
                this.create_certs();
            },
            create_certs: function() {
                this._render('create_certs_tmpl')
            },
            moveVideos: function() {
                this._render('move_videos_tmpl')
            },
            _render: function(id_name) {
                var template = $('#' + id_name).text();
                $('#right_content_main').html(_.template(template));
            }
        });

    });

})(define || RequireJS.define);
