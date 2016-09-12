define(['underscore'], function(_) {
    'use strict';

    var expectProfileElementContainsField = function(element, view) {
        var $element = $(element);
        var fieldTitle = $element.find('.u-field-title').text().trim();

        if (!_.isUndefined(view.options.title)) {
            expect(fieldTitle).toBe(view.options.title);
        }

        if ('fieldValue' in view || 'imageUrl' in view) {
            if ('imageUrl' in view) {
                expect($($element.find('.image-frame')[0]).attr('src')).toBe(view.imageUrl());
            } else if (view.fieldValue()) {
                expect(view.fieldValue()).toBe(view.modelValue());

            } else if ('optionForValue' in view) {
                expect($($element.find('.u-field-value .u-field-value-readonly')[0]).text()).toBe(view.displayValue(view.modelValue()));

            }else {
                expect($($element.find('.u-field-value .u-field-value-readonly')[0]).text()).toBe(view.modelValue());
            }
        } else {
            throw new Error('Unexpected field type: ' + view.fieldType);
        }
    };

    var expectProfilePrivacyFieldTobeRendered = function(learnerProfileView, othersProfile) {

        var accountPrivacyElement = learnerProfileView.$('.wrapper-profile-field-account-privacy');
        var privacyFieldElement = $(accountPrivacyElement).find('.u-field');

        if (othersProfile) {
            expect(privacyFieldElement.length).toBe(0);
        } else {
            expect(privacyFieldElement.length).toBe(1);
            expectProfileElementContainsField(privacyFieldElement, learnerProfileView.options.accountPrivacyFieldView);
        }
    };

    var expectSectionOneTobeRendered = function(learnerProfileView) {

        var sectionOneFieldElements = $(learnerProfileView.$('.wrapper-profile-section-one')).find('.u-field');

        expect(sectionOneFieldElements.length).toBe(4);
        expectProfileElementContainsField(sectionOneFieldElements[0], learnerProfileView.options.profileImageFieldView);
        expectProfileElementContainsField(sectionOneFieldElements[1], learnerProfileView.options.usernameFieldView);

        _.each(_.rest(sectionOneFieldElements, 2) , function (sectionFieldElement, fieldIndex) {
            expectProfileElementContainsField(
                sectionFieldElement,
                learnerProfileView.options.sectionOneFieldViews[fieldIndex]
            );
        });
    };

    var expectSectionTwoTobeRendered = function(learnerProfileView) {

        var sectionTwoElement = learnerProfileView.$('.wrapper-profile-section-two');
        var sectionTwoFieldElements = $(sectionTwoElement).find('.u-field');

        expect(sectionTwoFieldElements.length).toBe(learnerProfileView.options.sectionTwoFieldViews.length);

         _.each(sectionTwoFieldElements, function (sectionFieldElement, fieldIndex) {
            expectProfileElementContainsField(
                sectionFieldElement,
                learnerProfileView.options.sectionTwoFieldViews[fieldIndex]
            );
        });
    };

    var expectSectionThreeTobeRendered = function(learnerProfileView, othersProfile) {

        var sectionThreeElement = learnerProfileView.$('.wrapper-profile-section-three');
        var sectionThreeFieldElements = $(sectionThreeElement).find('.profile-private--privacy-message');

        if (othersProfile) {
            expect(sectionThreeFieldElements.text())
                .toBe('')
        } else {
            if (learnerProfileView.options.accountSettingsModel.isAboveMinimumAge()) {
                expect(sectionThreeFieldElements.text())
                    .toBe('Please do NOT input your personally identifiable information (PII) here. This part will be shared to another students.')
            } else {
                expect(sectionThreeFieldElements.text())
                    .toBe('');
            }
        }
    };

    var expectProfileSectionsAndFieldsToBeRendered = function (learnerProfileView, othersProfile) {
        expectProfilePrivacyFieldTobeRendered(learnerProfileView, othersProfile);
        expectSectionOneTobeRendered(learnerProfileView);
        expectSectionTwoTobeRendered(learnerProfileView);
        expectSectionThreeTobeRendered(learnerProfileView, othersProfile);
    };

    var expectLimitedProfileSectionsAndFieldsToBeRendered = function (learnerProfileView, othersProfile) {
        expectProfilePrivacyFieldTobeRendered(learnerProfileView, othersProfile);

        var sectionOneFieldElements = $(learnerProfileView.$('.wrapper-profile-section-one')).find('.u-field');

        expect(sectionOneFieldElements.length).toBe(2);
        expectProfileElementContainsField(
            sectionOneFieldElements[0],
            learnerProfileView.options.profileImageFieldView
        );
        expectProfileElementContainsField(
            sectionOneFieldElements[1],
            learnerProfileView.options.usernameFieldView
        );

        expectSectionThreeTobeRendered(learnerProfileView, othersProfile);

        if (othersProfile) {
            expect($('.profile-private--message').text())
                .toBe('');
        } else {
            if (learnerProfileView.options.accountSettingsModel.isAboveMinimumAge()) {
                expect($('.profile-private--message').text()).toBe('You are currently sharing a limited profile.');
            } else {
                expect($('.profile-private--message').text()).toBe('Children of age {parentalConsentAgeLimit} and under can NOT disclose their own profile information online.'.replace('{parentalConsentAgeLimit}', learnerProfileView.parentalConsentAgeLimit));
            }
        }
    };

    var expectProfileSectionsNotToBeRendered = function(learnerProfileView) {
        expect(learnerProfileView.$('.wrapper-profile-field-account-privacy').length).toBe(0);
        expect(learnerProfileView.$('.wrapper-profile-section-one').length).toBe(0);
        expect(learnerProfileView.$('.wrapper-profile-section-two').length).toBe(0);
        expect(learnerProfileView.$('.wrapper-profile-section-three').length).toBe(0);
    };

    return {
        expectLimitedProfileSectionsAndFieldsToBeRendered: expectLimitedProfileSectionsAndFieldsToBeRendered,
        expectProfileSectionsAndFieldsToBeRendered: expectProfileSectionsAndFieldsToBeRendered,
        expectProfileSectionsNotToBeRendered: expectProfileSectionsNotToBeRendered
    };
});
