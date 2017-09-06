;(function (define) {

    define(['backbone', 'underscore'], function (Backbone, _) {
        'use strict';

        return Backbone.Router.extend({
            routes: {
                "": "mutualGradingReport",
                "upload_certs_template": "uploadCertsTemplate",
                "create_certs": "createCerts",
                "create_certs_meeting": "createCertsMeeting",
                "publish_certs": "publishCerts",
                "move_videos": "moveVideos",
                "mutual_grading_report": "mutualGradingReport",
                "discussion_data": "discussionData",
                "past_graduates_info": "pastGraduatesInfo",
                "last_login_info": "lastLoginInfo",
                "aggregate_g1528": "aggregateG1528",
                "all_users_info": "allUsersInfo",
                "create_certs_status": "createCertsStatus",
                "enrollment_status": "enrollmentStatus",
                "disabled_account_info": "disabledAccountInfo",
            },
            uploadCertsTemplate: function() {
                this._render('upload_certs_template_tmpl');
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
            aggregateG1528: function () {
                this._render("aggregate_g1528_tmpl")
            },
            allUsersInfo: function () {
                this._render("all_users_info_tmpl")
            },
            createCertsStatus: function () {
                this._render("create_certs_status_tmpl")
            },
            enrollmentStatus: function () {
                this._render("enrollment_status_tmpl")
            },
            disabledAccountInfo: function () {
                this._render("disabled_account_info_tmpl")
            },
            _render: function(id_name) {
                $('#right_content_response').text('');
                var template = $('#' + id_name).text();
                $('#right_content_main').html(_.template(template));
            }
        });

    });

})(define || RequireJS.define);
