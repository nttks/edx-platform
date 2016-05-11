;(function (define) {

    define(['backbone', 'underscore'], function (Backbone, _) {
        'use strict';

        return Backbone.Router.extend({
            routes: {
                "": "mutualGradingReport",
                "create_certs": "createCerts",
                "create_certs_meeting": "createCertsMeeting",
                "publish_certs": "publishCerts",
                "move_videos": "moveVideos",
                "mutual_grading_report": "mutualGradingReport",
                "discussion_data": "discussionData",
                "past_graduates_info": "pastGraduatesInfo",
                "last_login_info": "lastLoginInfo"
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
            mutualGradingReport: function () {
                this._render("mutual_grading_report_tmpl")
            },
            discussionData: function () {
                this._render("discussion_data_tmpl")
            },
            pastGraduatesInfo: function () {
                this._render("past_graduates_info_tmpl")
            },
            lastLoginInfo: function () {
                this._render("last_login_info_tmpl")
            },
            _render: function(id_name) {
                $('#right_content_response').text('');
                var template = $('#' + id_name).text();
                $('#right_content_main').html(_.template(template));
            }
        });

    });

})(define || RequireJS.define);
