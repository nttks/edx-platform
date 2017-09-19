;(function (define, undefined) {
    'use strict';
    define([
        'gettext', 'jquery', 'underscore', 'backbone',
        'text!templates/student_profile/field_own_certificates.underscore',
        'text!templates/student_profile/field_public_certificates.underscore'],

        function (gettext, $, _, Backbone, fieldOwnCertificatesTemplate, fieldPublicCertificatesTemplate) {

        var FieldCertificates = Backbone.View.extend({
            initialize: function () {
                _.bindAll(this, 'render', 'setProfileVisibility');
            },

            events: {
                'change .cert-visibility-change': 'certVisibilityChange'
            },

            render: function () {
                var certInfos = this.options.certInfos;
                var profileVisibility = this.options.profileVisibility;

                if (this.options.ownProfile) {
                    this.undelegateEvents();
                    this.$el.html(_.template(fieldOwnCertificatesTemplate, {
                        certInfos: certInfos,
                        profileVisibility: profileVisibility
                    }));
                    this.delegateEvents();
                } else {
                    this.undelegateEvents();
                    this.$el.html(_.template(fieldPublicCertificatesTemplate, {
                        certInfos: certInfos
                    }));
                    // do not call delegateEvents for visibilities are not changed by other users
                }
                return this
            },

            certVisibilityChange: function (event) {
                var render = this.render;
                var headers = {
                    'X-CSRFToken': $.cookie('csrftoken')
                };

                $.ajax({
                    url: '/certs_visibility/' + $(event.target).data('course-id') + '/',
                    type: 'POST',
                    data: {is_visible_to_public: event.target.value},
                    headers: headers
                })
                .done(function() {
                })
                .fail(function() {
                    render();
                });
            },

            setProfileVisibility: function (visibility) {
                this.options.profileVisibility = visibility;
            }
        });

        return FieldCertificates;
    });
}).call(this, define || RequireJS.define);
