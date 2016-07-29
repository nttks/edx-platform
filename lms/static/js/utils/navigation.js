var edx = edx || {},

    Navigation = (function() {

        var navigation = {

            ROOT_ID_PC: '#accordion',
            ROOT_ID_SP: '#modal-accordion',

            init: function(isModal) {
                var rootId = isModal ? navigation.ROOT_ID_SP : navigation.ROOT_ID_PC;
                if ($(rootId + '.accordion').length) {
                    navigation.loadAccordion(rootId);
                }
            },

            loadAccordion: function(rootId) {
                navigation.checkForCurrent(rootId);
                navigation.listenForClick(rootId);
                navigation.listenForKeypress(rootId);
            },

            getActiveIndex: function(rootId) {
                var index = $(rootId + '.accordion .button-chapter:has(.active)').index(rootId + '.accordion .button-chapter'),
                    button = null;

                if (index > -1) {
                    button = $(rootId + '.accordion .button-chapter:eq(' + index + ')');
                }

                return button;
            },

            checkForCurrent: function(rootId) {
                var button = navigation.getActiveIndex(rootId);

                navigation.closeAccordions(button);

                if (button !== null) {
                    navigation.setupCurrentAccordionSection(button);
                }
            },

            listenForClick: function(rootId) {
                $(rootId + '.accordion').on('click', '.button-chapter', function(event) {
                    event.preventDefault();

                    var button = $(event.currentTarget),
                        section = button.next('.chapter-content-container');

                    navigation.closeAccordions(button, section);
                    navigation.openAccordion(button, section);
                });
            },

            listenForKeypress: function(rootId) {
                $(rootId + '.accordion').on('keydown', '.button-chapter', function(event) {
                    // because we're changing the role of the toggle from an 'a' to a 'button'
                    // we need to ensure it has the same keyboard use cases as a real button.
                    // this is useful for screenreader users primarily.
                    if (event.which == 32) { // spacebar
                        event.preventDefault();
                        $(event.currentTarget).trigger('click');
                    } else {
                        return true;
                    }
                });
            },

            closeAccordions: function(button, section) {
                var menu = $(section).find('.chapter-menu'), toggle;

                button.parents('.accordion').find('.button-chapter').each(function(index, element) {
                    toggle = $(element);

                    toggle
                        .removeClass('is-open')
                        .attr('aria-expanded', 'false');

                    toggle
                        .children('.group-heading')
                        .removeClass('active')
                        .find('.icon')
                            .addClass('fa-caret-right')
                            .removeClass('fa-caret-down');

                    toggle
                        .next('.chapter-content-container')
                        .removeClass('is-open')
                        .find('.chapter-menu').not(menu)
                            .removeClass('is-open')
                            .slideUp();

                    toggle.parents('.chapter-wrapper').removeClass('is-open');
                });
            },

            setupCurrentAccordionSection: function(button) {
                var section = $(button).next('.chapter-content-container');

                navigation.openAccordion(button, section);
            },

            openAccordion: function(button, section) {
                var sectionEl = $(section),
                    firstLink = sectionEl.find('.menu-item').first(),
                    buttonEl = $(button);

                buttonEl
                    .addClass('is-open')
                    .attr('aria-expanded', 'true');

                buttonEl
                    .children('.group-heading')
                    .addClass('active')
                    .find('.icon')
                        .removeClass('fa-caret-right')
                        .addClass('fa-caret-down');

                sectionEl
                    .addClass('is-open')
                    .find('.chapter-menu')
                        .addClass('is-open')
                        .slideDown();

                buttonEl.parents('.chapter-wrapper').addClass('is-open');
            }
        };

        return {
            init: navigation.init
        };

    })();

    edx.util = edx.util || {};
    edx.util.navigation = Navigation;
    edx.util.navigation.init();
    edx.util.navigation.init(true);
