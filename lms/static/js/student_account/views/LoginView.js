;(function (define) {
    'use strict';
    define([
            'jquery',
            'underscore',
            'gettext',
            'js/student_account/views/FormView',
            'js/query-params'
        ],
        function($, _, gettext, FormView) {

        return FormView.extend({
            el: '#login-form',
            tpl: '#login-tpl',
            events: {
                'click .js-login': 'submitForm',
                'click .forgot-password': 'forgotPassword',
                'click .login-provider': 'thirdPartyAuth'
            },
            formType: 'login',
            requiredStr: '',
            submitButton: '.js-login',

            preRender: function( data ) {
                this.providers = data.thirdPartyAuth.providers || [];
                this.hasSecondaryProviders = (
                    data.thirdPartyAuth.secondaryProviders && data.thirdPartyAuth.secondaryProviders.length
                );
                this.currentProvider = data.thirdPartyAuth.currentProvider || '';
                this.errorMessage = data.thirdPartyAuth.errorMessage || '';
                this.platformName = data.platformName;
                this.resetModel = data.resetModel;

                this.listenTo( this.model, 'sync', this.saveSuccess );
                this.listenTo( this.resetModel, 'sync', this.resetEmail );
            },

            render: function( html ) {
                var fields = html || '';

                $(this.el).html( _.template( this.tpl, {
                    // We pass the context object to the template so that
                    // we can perform variable interpolation using sprintf
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

                return this;
            },

            postRender: function() {
                this.$container = $(this.el);

                this.$form = this.$container.find('form');
                this.$errors = this.$container.find('.submission-error');
                this.$resetSuccess = this.$container.find('.js-reset-success');
                this.$authError = this.$container.find('.already-authenticated-msg');
                this.$submitButton = this.$container.find(this.submitButton);
                this.$activateAccountNotice = this.$container.find('.activate-account-notice');

                /* If we're already authenticated with a third-party
                 * provider, try logging in.  The easiest way to do this
                 * is to simply submit the form.
                 */
                if (this.currentProvider) {
                    this.model.save();
                }

                if (getParameterByName('unactivated')) {
                    this.activateAccountNotice();
                }
            },

            forgotPassword: function( event ) {
                event.preventDefault();

                this.trigger('password-help');
                this.element.hide( this.$resetSuccess );
            },

            postFormSubmission: function() {
                this.element.hide( this.$activateAccountNotice );
                this.element.hide( this.$resetSuccess );
            },

            resetEmail: function() {
                this.element.hide( this.$errors );
                this.element.show( this.$resetSuccess );
            },

            thirdPartyAuth: function( event ) {
                var providerUrl = $(event.currentTarget).data('provider-url') || '';

                if (providerUrl) {
                    window.location.href = providerUrl;
                }
            },

            saveSuccess: function() {
                this.trigger('auth-complete');
                this.element.hide( this.$resetSuccess );
            },

            activateAccountNotice: function() {
                this.element.show( this.$activateAccountNotice );
            },

            saveError: function( error ) {
                var msg = error.responseText;
                if (error.status === 0) {
                    msg = gettext('An error has occurred. Check your Internet connection and try again.');
                } else if(error.status === 500){
                    msg = gettext('An error has occurred. Try refreshing the page, or check your Internet connection.');
                }
                this.errors = ['<li>' + msg + '</li>'];
                this.setErrors();
                this.element.hide( this.$resetSuccess );

                /* If we've gotten a 403 error, it means that we've successfully
                 * authenticated with a third-party provider, but we haven't
                 * linked the account to an EdX account.  In this case,
                 * we need to prompt the user to enter a little more information
                 * to complete the registration process.
                 */
                if ( error.status === 403 &&
                     error.responseText === 'third-party-auth' &&
                     this.currentProvider ) {
                    this.element.show( this.$authError );
                    this.element.hide( this.$errors );
                } else {
                    this.element.hide( this.$authError );
                    this.element.show( this.$errors );
                }
                this.toggleDisableButton(false);
            },

            getQueryString: function() {
                var obj = {}, param, set, i;
                param = location.search.substring(1).split('&');
                for( i=0; i<param.length; i++ ) {
                    if (param[i].search(/=/) !== -1) {
                        set = param[i].split('=');
                        if(set[0] !== '') {
                            obj[set[0]] = set[1];
                        }
                    }
                }
                return obj;
            },

            customValidate: function() {
                var _this = this,
                    qs = this.getQueryString(),
                    $el = null,
                    email = '',
                    response_data = null,
                    i,
                    elements;

                // get email from input
                elements = this.$form[0].elements;
                for ( i=0; i<elements.length; i++ ) {
                    $el = $( elements[i] );
                    if ($el.attr('name') === 'email') {
                        email = $el.val();
                        break;
                    }
                }

                // ajax request
                $.ajax({
                    url: '/ga_student_account/check_redirect_saml_login',
                    type: 'post',
                    headers: {'X-CSRFToken': $.cookie('csrftoken')},
                    data: { email: email, next: qs.next || '' },
                    async: false
                }).done(function( data ) {
                    if (data.exist_saml_master && data.redirect_url) {
                        response_data = data;
                    }
                });

                if (response_data) {
                    // Set dummy error and stop errors display, because redirect to saml login page.
                    _this.setErrors = function() {};
                    this.errors.push(true);

                    // Redirect to saml login page.
                    location.href = response_data.redirect_url;
                }
            }
        });
    });
}).call(this, define || RequireJS.define);

