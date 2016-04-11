;(function (define) {

    define(['backbone', 'underscore'], function (Backbone, _) {
        'use strict';

        return Backbone.Router.extend({
            routes: {
                '': 'createCerts',
                'create_certs': 'createCerts',
                'create_certs_meeting': 'createCertsMeeting',
                'publish_certs': 'publishCerts',
                'move_videos': 'moveVideos'
            },
            createCerts: function() {
                this._render('create_certs_tmpl')
            },
            createCertsMeeting: function() {
                this._render('create_certs_meeting_tmpl')
            },
            publishCerts: function() {
                this._render('publish_certs_tmpl')
            },
            moveVideos: function() {
                this._render('move_videos_tmpl')
            },
            _render: function(id_name) {
                $('#right_content_response').text('');
                var template = $('#' + id_name).text();
                $('#right_content_main').html(_.template(template));
            }
        });

    });

})(define || RequireJS.define);
