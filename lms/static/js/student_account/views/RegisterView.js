;(function (define) {
    'use strict';
    define([
            'jquery',
            'underscore',
            'js/student_account/views/FormView'
        ],
        function($, _, FormView) {

        return FormView.extend({
            el: '#register-form',

            tpl: '#register-tpl',

            events: {
                'click .js-register': 'submitForm',
                'click .login-provider': 'thirdPartyAuth'
            },

            formType: 'register',

            submitButton: '.js-register',

            orgUsernameRule: [],

            preRender: function( data ) {
                this.providers = data.thirdPartyAuth.providers || [];
                this.hasSecondaryProviders = (
                    data.thirdPartyAuth.secondaryProviders && data.thirdPartyAuth.secondaryProviders.length
                );
                this.currentProvider = data.thirdPartyAuth.currentProvider || '';
                this.errorMessage = data.thirdPartyAuth.errorMessage || '';
                this.platformName = data.platformName;
                this.autoSubmit = data.thirdPartyAuth.autoSubmitRegForm;

                this.listenTo( this.model, 'sync', this.saveSuccess );

                this.getUsernameRules();
            },

            getUsernameRules: function() {
                var _this = this;
                $.ajax({
                    url: "/ga_student_account/get_org_username_rules",
                    headers: {'X-CSRFToken': $.cookie('csrftoken')},
                }).done(function(data) {
                    if (data.list) {
                        _this.orgUsernameRule = JSON.parse(data.list);
                    }
                }).fail(function() {
                    console.log('error');
                });
            },

            render: function( html ) {
                var fields = html || '';

                $(this.el).html( _.template( this.tpl, {
                    /* We pass the context object to the template so that
                     * we can perform variable interpolation using sprintf
                     */
                    context: {
                        fields: fields,
                        currentProvider: this.currentProvider,
                        errorMessage: this.errorMessage,
                        providers: this.providers,
                        hasSecondaryProviders: this.hasSecondaryProviders,
                        platformName: this.platformName
                    }
                }));

                this.postRender();

                if (this.autoSubmit) {
                    $(this.el).hide();
                    $('#register-honor_code').prop('checked', true);
                    this.submitForm();
                }

                return this;
            },

            thirdPartyAuth: function( event ) {
                var providerUrl = $(event.currentTarget).data('provider-url') || '';

                if ( providerUrl ) {
                    window.location.href = providerUrl;
                }
            },

            saveSuccess: function() {
                this.trigger('auth-complete');
            },

            saveError: function( error ) {
                $(this.el).show(); // Show in case the form was hidden for auto-submission
                this.errors = _.flatten(
                    _.map(
                        JSON.parse(error.responseText),
                        function(error_list) {
                            return _.map(
                                error_list,
                                function(error) { return '<li>' + error.user_message + '</li>'; }
                            );
                        }
                    )
                );
                this.setErrors();
                this.toggleDisableButton(false);
            },

            postFormSubmission: function() {
                if (_.compact(this.errors).length) {
                    // The form did not get submitted due to validation errors.
                    $(this.el).show(); // Show in case the form was hidden for auto-submission
                }
            },

            customValidate: function( data ) {
                var errors = [];
                // Confirm whether it applies to ng rules.
                _.every(this.orgUsernameRule, function(rule) {
                    if ((data.username).match(new RegExp('^' + rule, 'gi')) != null) {
                        errors.push(gettext('The user name you entered is already in use.'));
                        return false;
                    }
                });
                this.errors = _.union(this.errors, errors);
            }
        });
    });
}).call(this, define || RequireJS.define);
