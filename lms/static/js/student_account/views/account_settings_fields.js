;(function (define, undefined) {
    'use strict';
    define([
        'gettext', 'jquery', 'underscore', 'backbone', 'js/views/fields'
    ], function (gettext, $, _, Backbone, FieldViews) {

        var AccountSettingsFieldViews = {};

        AccountSettingsFieldViews.EmailFieldView = FieldViews.TextFieldView.extend({

            successMessage: function() {
                return this.indicators.success + interpolate_text(
                    gettext(
                        /* jshint maxlen: false */
                        'We\'ve sent a confirmation message to {new_email_address}. Click the link in the message to update your email address.'
                    ),
                    {'new_email_address': this.fieldValue()}
                );
            }
        });

        AccountSettingsFieldViews.LanguagePreferenceFieldView = FieldViews.DropdownFieldView.extend({

            saveSucceeded: function () {
                var data = {
                    'language': this.modelValue()
                };

                var view = this;
                $.ajax({
                    type: 'POST',
                    url: '/i18n/setlang/?clear-lang',
                    data: data,
                    dataType: 'html',
                    success: function () {
                        view.showSuccessMessage();
                    },
                    error: function () {
                        view.showNotificationMessage(
                            view.indicators.error +
                                gettext('You must sign out and sign back in before your language changes take effect.')
                        );
                    }
                });
            }

        });

        AccountSettingsFieldViews.PasswordFieldView = FieldViews.LinkFieldView.extend({

            initialize: function (options) {
                this._super(options);
                _.bindAll(this, 'resetPassword');
            },

            linkClicked: function (event) {
                event.preventDefault();
                this.resetPassword(event);
            },

            resetPassword: function () {
                var data = {};
                data[this.options.emailAttribute] = this.model.get(this.options.emailAttribute);

                var view = this;
                $.ajax({
                    type: 'POST',
                    url: view.options.linkHref,
                    data: data,
                    success: function () {
                        view.showSuccessMessage();
                    },
                    error: function (xhr) {
                        view.showErrorMessage(xhr);
                    }
                });
            },

            successMessage: function () {
                return this.indicators.success + interpolate_text(
                    gettext(
                        /* jshint maxlen: false */
                        'We\'ve sent a message to {email_address}. Click the link in the message to reset your password.'
                    ),
                    {'email_address': this.model.get(this.options.emailAttribute)}
                );
            }
        });

        AccountSettingsFieldViews.ResignFieldView = FieldViews.LinkFieldView.extend({

            initialize: function(options){
                this._super(options);
                _.bindAll(this, 'resign');
            },

            linkClicked: function(event){
                event.preventDefault();
                this.resign(event);
            },

            resign: function(){
                var data = {};
                data[this.options.emailAttribute] = this.model.get(this.options.emailAttribute);

                var view = this;
                $.ajax({
                    type: 'POST',
                    url: view.options.linkHref,
                    data: data,
                    success: function () {
                        view.showSuccessMessage();
                    },
                    error: function (xhr) {
                        view.showErrorMessage(xhr);
                    }
                });
            },

            successMessage: function () {
                return this.indicators.success + interpolate_text(
                    gettext(
                        'An email has been sent to {email_address}. ' +
                        'Follow the link in the email to resign.'
                    ),
                    {'email_address': this.model.get(this.options.emailAttribute)}
                );
            }

        });

        AccountSettingsFieldViews.InvitationCodeFieldView = FieldViews.LinkFieldView.extend({

            linkClicked: function(event){
                event.preventDefault();
                window.location.href = this.options.linkHref;
            },

        });

        AccountSettingsFieldViews.ReceiveEmailFieldView = FieldViews.LinkFieldView.extend({

            isProcessing: false,
            receiveEmailStatus: null,

            render: function () {
                var view = this;

                if (!view.options.hasGlobalCourse) {
                    view.$el.hide();
                    return view;
                }

                view._super();
                view.$el.find('#u-field-link-receive_email').after($('<span>'));

                view.setText(view.options.loading);
                $.ajax({
                    type: 'GET',
                    url: view.options.linkHref,
                }).done(function(data) {
                    view.receiveEmailStatus = data.is_receive_email ? 'optin': 'optout';
                    view.setText(view.options[view.receiveEmailStatus]);
                }).fail(function(jqXHR) {
                    view.showErrorMessage(jqXHR);
                });

                return view;
            },

            setText: function(targetOptions) {
                this.$el.find('span.u-field-link-title-receive_email').html(targetOptions.linkTitle);
                this.$el.find('#u-field-link-receive_email+span').text(targetOptions.caption);
            },

            linkClicked: function(event) {
                var view = this,
                    currentStatus = view.receiveEmailStatus,
                    reverseStatus = targetOptions = null;

                event.preventDefault();

                if (currentStatus == null || view.isProcessing) {
                    return;
                }

                view.isProcessing = true;
                view.setText(view.options.loading);

                reverseStatus = view.options[currentStatus].reverseStatus;
                targetOptions = view.options[reverseStatus];

                $.ajax({
                    type: targetOptions.methodType,
                    url: view.options.linkHref,
                }).done(function() {
                    view.setText(targetOptions);
                    view.receiveEmailStatus = reverseStatus;
                    view.showSuccessMessage();
                }).fail(function(jqXHR) {
                    view.setText(view.options[currentStatus]);
                    view.showErrorMessage(jqXHR);
                }).always(function() {
                    view.isProcessing = false;
                });
            },

        });

        AccountSettingsFieldViews.LanguageProficienciesFieldView = FieldViews.DropdownFieldView.extend({

            modelValue: function () {
                var modelValue = this.model.get(this.options.valueAttribute);
                if (_.isArray(modelValue) && modelValue.length > 0) {
                    return modelValue[0].code;
                } else {
                    return null;
                }
            },

            saveValue: function () {
                if (this.persistChanges === true) {
                    var attributes = {},
                        value = this.fieldValue() ? [{'code': this.fieldValue()}] : [];
                    attributes[this.options.valueAttribute] = value;
                    this.saveAttributes(attributes);
                }
            }
        });

        AccountSettingsFieldViews.AuthFieldView = FieldViews.LinkFieldView.extend({

            initialize: function (options) {
                this._super(options);
                _.bindAll(this, 'redirect_to', 'disconnect', 'successMessage', 'inProgressMessage');
            },

            render: function () {
                var linkTitle;
                if (this.options.connected) {
                    linkTitle = gettext('Unlink');
                } else if (this.options.acceptsLogins) {
                    linkTitle = gettext('Link')
                } else {
                    linkTitle = ''
                }

                this.$el.html(this.template({
                    id: this.options.valueAttribute,
                    title: this.options.title,
                    screenReaderTitle: this.options.screenReaderTitle,
                    linkTitle: linkTitle,
                    linkHref: '',
                    message: this.helpMessage
                }));
                return this;
            },

            linkClicked: function (event) {
                event.preventDefault();

                this.showInProgressMessage();

                if (this.options.connected) {
                    this.disconnect();
                } else {
                    // Direct the user to the providers site to start the authentication process.
                    // See python-social-auth docs for more information.
                    this.redirect_to(this.options.connectUrl);
                }
            },

            redirect_to: function (url) {
                window.location.href = url;
            },

            disconnect: function () {
                var data = {};

                // Disconnects the provider from the user's edX account.
                // See python-social-auth docs for more information.
                var view = this;
                $.ajax({
                    type: 'POST',
                    url: this.options.disconnectUrl,
                    data: data,
                    dataType: 'html',
                    success: function () {
                        view.options.connected = false;
                        view.render();
                        view.showSuccessMessage();
                    },
                    error: function (xhr) {
                        view.showErrorMessage(xhr);
                    }
                });
            },

            inProgressMessage: function() {
                return this.indicators.inProgress + (this.options.connected ? gettext('Unlinking') : gettext('Linking'));
            },

            successMessage: function() {
                return this.indicators.success + gettext('Successfully unlinked.');
            }
        });

        return AccountSettingsFieldViews;
    });
}).call(this, define || RequireJS.define);
