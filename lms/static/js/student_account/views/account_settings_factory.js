;(function (define, undefined) {
    'use strict';
    define([
        'gettext', 'jquery', 'underscore', 'backbone', 'logger',
        'js/views/fields',
        'js/student_account/models/user_account_model',
        'js/student_account/models/user_preferences_model',
        'js/student_account/views/account_settings_fields',
        'js/student_account/views/account_settings_view'
    ], function (gettext, $, _, Backbone, Logger, FieldViews, UserAccountModel, UserPreferencesModel,
                 AccountSettingsFieldViews, AccountSettingsView) {

        return function (fieldsData, authData, userAccountsApiUrl, userPreferencesApiUrl, accountUserId, platformName, emailHiddenAvailable) {

            var accountSettingsElement = $('.wrapper-account-settings');

            var userAccountModel = new UserAccountModel();
            userAccountModel.url = userAccountsApiUrl;

            var userPreferencesModel = new UserPreferencesModel();
            userPreferencesModel.url = userPreferencesApiUrl;

            var basicAccountInformationFields = [];
            basicAccountInformationFields.push(
                {
                    view: new FieldViews.ReadonlyFieldView({
                        model: userAccountModel,
                        title: gettext('Username'),
                        valueAttribute: 'username',
                        helpMessage: interpolate_text(
                            gettext('The name that identifies you throughout {platform_name}. You cannot change your username.'), {platform_name: platformName}
                        )
                    })
                }
            );
            basicAccountInformationFields.push(
                {
                    view: new FieldViews.TextFieldView({
                        model: userAccountModel,
                        title: gettext('Full Name'),
                        valueAttribute: 'name',
                        helpMessage: gettext('The name that appears on your certificates. Other learners never see your full name.'),
                        persistChanges: true
                    })
                }
            );
            if (!emailHiddenAvailable) {
                basicAccountInformationFields.push(
                    {
                        view: new AccountSettingsFieldViews.EmailFieldView({
                            model: userAccountModel,
                            title: gettext('Email Address'),
                            valueAttribute: 'email',
                            helpMessage: interpolate_text(
                                gettext('The email address you use to sign in. Communications from {platform_name} and your courses are sent to this address.'), {platform_name: platformName}
                            ),
                            persistChanges: true
                        })
                    }
                );
            }
            basicAccountInformationFields.push(
                {
                    view: new AccountSettingsFieldViews.PasswordFieldView({
                        model: userAccountModel,
                        title: gettext('Password'),
                        screenReaderTitle: gettext('Reset your Password'),
                        valueAttribute: 'password',
                        emailAttribute: 'email',
                        linkTitle: gettext('Reset Password'),
                        linkHref: fieldsData.password.url,
                        helpMessage: gettext('When you click "Reset Password", a message will be sent to your email address. Click the link in the message to reset your password.')
                    })
                }
            );
            basicAccountInformationFields.push(
                {
                    view: new AccountSettingsFieldViews.LanguagePreferenceFieldView({
                        model: userPreferencesModel,
                        title: gettext('Language'),
                        valueAttribute: 'pref-lang',
                        required: true,
                        refreshPageOnSave: true,
                        helpMessage: interpolate_text(
                            gettext('The language used throughout this site. This site is currently available in a limited number of languages.'), {platform_name: platformName}
                        ),
                        options: fieldsData.language.options,
                        persistChanges: true
                    })
                }
            );

            var sectionsData = [
                {
                    title: gettext('Basic Account Information (required)'),
                    fields: basicAccountInformationFields
                },
                {
                    title: gettext('Additional Information (optional)'),
                    fields: [
                        {
                            view: new FieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Education Completed'),
                                valueAttribute: 'level_of_education',
                                options: fieldsData.level_of_education.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new FieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Gender'),
                                valueAttribute: 'gender',
                                options: fieldsData.gender.options,
                                persistChanges: true
                            })
                        },
                        {
                            view: new FieldViews.DropdownFieldView({
                                model: userAccountModel,
                                title: gettext('Year of Birth'),
                                valueAttribute: 'year_of_birth',
                                options: fieldsData['year_of_birth']['options'],
                                persistChanges: true
                            })
                        }
                    ]
                },
                {
                    title: gettext('Other procedures'),
                    fields: [
                        {
                            view: new AccountSettingsFieldViews.ReceiveEmailFieldView({
                                model: userAccountModel,
                                title: gettext('E-mail magazine delivery settings'),
                                valueAttribute: 'receive_email',
                                linkTitle: '',
                                linkHref: fieldsData.receive_email.url,
                                hasGlobalCourse: fieldsData.receive_email.has_global_course,
                                optout: {
                                    linkTitle: '&#xf204;',
                                    caption: gettext('Resume delivery'),
                                    methodType: 'DELETE',
                                    reverseStatus: 'optin',
                                },
                                optin: {
                                    linkTitle: '&#xf205;',
                                    caption: gettext('Stop delivery'),
                                    methodType: 'PUT',
                                    reverseStatus: 'optout',
                                },
                                loading: {
                                    linkTitle: '&#xf021;',
                                    caption: gettext('Working'),
                                },
                                helpMessage: interpolate_text(
                                    gettext('You can set the e-mail magazine delivery from {platform_name}. The delivery is to stop/resume and click on the icon to the left. E-mail received from each course can be set from My page.'),
                                    {platform_name: platformName}
                                )
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.InvitationCodeFieldView({
                                model: userAccountModel,
                                title: gettext('Invitation Code'),
                                valueAttribute: 'invitation_code',
                                linkTitle: gettext('Manage invitation code.'),
                                linkHref: fieldsData.invitation_code.url,
                                helpMessage: gettext('If you have invitation code, click the link and manage invitation code.')
                            })
                        },
                        {
                            view: new AccountSettingsFieldViews.ResignFieldView({
                                model: userAccountModel,
                                title: gettext('Resign'),
                                screenReaderTitle: gettext('Resign'),
                                valueAttribute: 'resign',
                                emailAttribute: 'email',
                                linkTitle: gettext('Resign'),
                                linkHref: fieldsData.resign.url,
                                helpMessage: gettext('When you click "Resign", a message will be sent to your email address. Click the link in the message to resign.')
                            })
                        }
                    ]
                }
            ];

            if (_.isArray(authData.providers)) {
                var accountsSectionData = {
                    title: gettext('Connected Accounts'),
                    fields: _.map(authData.providers, function(provider) {
                        return {
                            'view': new AccountSettingsFieldViews.AuthFieldView({
                                title: provider.name,
                                screenReaderTitle: interpolate_text(
                                    gettext("Connect your {accountName} account"), {accountName: provider['name']}
                                ),
                                valueAttribute: 'auth-' + provider.id,
                                helpMessage: '',
                                connected: provider.connected,
                                connectUrl: provider.connect_url,
                                acceptsLogins: provider.accepts_logins,
                                disconnectUrl: provider.disconnect_url
                            })
                        };
                    })
                };
                sectionsData.push(accountsSectionData);
            }

            var accountSettingsView = new AccountSettingsView({
                model: userAccountModel,
                accountUserId: accountUserId,
                el: accountSettingsElement,
                sectionsData: sectionsData
            });

            accountSettingsView.render();

            var showLoadingError = function () {
                accountSettingsView.showLoadingError();
            };

            var showAccountFields = function () {
                // Record that the account settings page was viewed.
                Logger.log('edx.user.settings.viewed', {
                    page: "account",
                    visibility: null,
                    user_id: accountUserId
                });

                // Render the fields
                accountSettingsView.renderFields();
            };

            userAccountModel.fetch({
                success: function () {
                    // Fetch the user preferences model
                    userPreferencesModel.fetch({
                        success: showAccountFields,
                        error: showLoadingError
                    });
                },
                error: showLoadingError
            });

            return {
                userAccountModel: userAccountModel,
                userPreferencesModel: userPreferencesModel,
                accountSettingsView: accountSettingsView
            };
        };
    });
}).call(this, define || RequireJS.define);
