(function(define) {
'use strict';
// VideoEndedModal module.
define(
'video/096_ended_modal.js', [],
function() {
    /**
     * Video Ended Modal module.
     * @exports video/096_ended_modal.js
     * @constructor
     * @param {jquery Element} element
     * @param {Object} options
     */
    var VideoEndedModal = function(state) {
        if (!(this instanceof VideoEndedModal)) {
            return new VideoEndedModal(state);
        }

        _.bindAll(this, 'render', 'destroy', 'onResize', 'onEnded');

        this.state = state;
        if (state.config.isStatusManaged){
            this.initialize();
        }
    };

    VideoEndedModal.moduleName = 'VideoEndedModal';
    VideoEndedModal.prototype = {
        template: [
            '<div class="video_ended_modal">',
                '<p class="video_ended_modal-msg">',
                    gettext('Would you like to view it already?'),
                '</p>',
                '<button class="video_ended_modal-button yes" type="button" data-ended="1">',
                    gettext('Yes'),
                '</button>',
                '<button class="video_ended_modal-button no" type="button" data-ended="0">',
                    gettext('No'),
                '</button>',
            '</div>'
        ].join(''),

        /** Initializes the module. */
        initialize: function() {
            this.el = $(this.template);
            this.render();
            this.bindHandlers();
        },

        /**
         * Creates any necessary DOM elements, attach them, and set their,
         * initial configuration.
         */
        render: function() {
            this.state.el.find('.tc-wrapper').append(this.el);
        },

        bindHandlers: function() {
            this.state.el.find('.tc-wrapper .video_ended_modal button').on('click', function() {
                var $this = $(this);
                var _url = $('.finish_playback_mongo').data("url");
                if ($this.data('ended') == '1') {
                    // Yes is ajax access
                    $.ajax({
                        url: _url,
                        data: {
                            data: 'Yes',
                            'module_id': $this.closest('.video-module_id').data('module_id'),
                        },
                        type: 'POST',
                    }).done(function () {
                    }).fail(function () {
                    }).always(function () {
                        $this.parent().hide();
                    });
                } else {
                    // No is not something
                    $.ajax({
                        url: _url,
                        data: {data: 'No',
                               'module_id': $this.closest('.video-module_id').data('module_id'),
                        } ,
                        type: 'POST',
                    }).done(function () {
                    }).fail(function () {
                    }).always(function () {
                        $this.parent().hide();
                    });
                }
            });
            this.state.el.on('ended', this.onEnded);
            this.state.el.on('endedModal:resize', this.onResize);
            this.state.el.on('fullscreen', this.onResize);
        },

        _getModal: function() {
            return $(this.state.el.find('.tc-wrapper')[0]).find(".video_ended_modal");
        },

        _setPositionToCenter: function($wrapper, $inner) {
            return $inner.css({
                'top': ($wrapper.innerHeight() - $inner.innerHeight()) / 2 + "px",
                'left': ($wrapper.innerWidth() - $inner.innerWidth()) / 2 + "px"
            });
        },

        onEnded: function() {
            var $this = $(this);
            var _url = $('.search_playback_mongo').data("url");
            $.ajax({
                url: _url,
                data:{
                    'block_id': $this[0].state.el.closest('.video-module_id').data('module_id')
                },
                type: 'POST',
            }).done(function (data) {
                if (!data['find_result']){
                    $this[0]._setPositionToCenter($this[0].state.el, $this[0]._getModal()).show();
                }
            });
        },

        showModal: function() {
            this._setPositionToCenter(this.state.el, this._getModal()).show();
        },

        onResize: function() {
            this._setPositionToCenter(this.state.el, this._getModal());
       },

        destroy: function() {}
    };

    return VideoEndedModal;
});
}(RequireJS.define));
