
define(["js/views/baseview", "underscore"], function(BaseView, _) {
    var AbstractEditor = BaseView.extend({

        // Model is MetadataModel
        initialize : function() {
            var self = this;
            var templateName = _.result(this, 'templateName');
            // Backbone model cid is only unique within the collection.
            this.uniqueId = _.uniqueId(templateName + "_");
            if (this.options.type == 'library_content' && this.model.attributes.field_name == 'max_count') {
                this.max_count_id = this.uniqueId;
            }
            this.template = this.loadTemplate(templateName);
            this.$el.html(this.template({model: this.model, uniqueId: this.uniqueId}));
            this.listenTo(this.model, 'change', this.render);
            this.render();
        },

        /**
         * The ID/name of the template. Subclasses must override this.
         */
        templateName: '',

        /**
         * Returns the value currently displayed in the editor/view. Subclasses should implement this method.
         */
        getValueFromEditor : function () {},

        /**
         * Sets the value currently displayed in the editor/view. Subclasses should implement this method.
         */
        setValueInEditor : function (value) {},

        /**
         * Sets the value in the model, using the value currently displayed in the view.
         */
        updateModel: function () {
            this.model.setValue(this.getValueFromEditor());
        },

        /**
         * Clears the value currently set in the model (reverting to the default).
         */
        clear: function () {
            this.model.clear();
        },

        /**
         * Shows the clear button, if it is not already showing.
         */
        showClearButton: function() {
            if (!this.$el.hasClass('is-set')) {
                this.$el.addClass('is-set');
                this.getClearButton().removeClass('inactive');
                this.getClearButton().addClass('active');
            }
        },

        /**
         * Returns the clear button.
         */
        getClearButton: function () {
            return this.$el.find('.setting-clear');
        },

        /**
         * Renders the editor, updating the value displayed in the view, as well as the state of
         * the clear button.
         */
        render: function () {
            if (!this.template) return;

            this.setValueInEditor(this.model.getDisplayValue());

            if (this.model.isExplicitlySet()) {
                this.showClearButton();
            }
            else {
                this.$el.removeClass('is-set');
                this.getClearButton().addClass('inactive');
                this.getClearButton().removeClass('active');
            }

            if (this.max_count_id){
                if (this.$('#' + this.max_count_id)[0].value < 1) {
                    self.$('#' + this.max_count_id + '-error').text(gettext('Please enter a value one or more'));
                    self.$('.action-save').addClass('is-disabled');
                } else {
                    self.$('#' + this.max_count_id + '-error').text('');
                    self.$('.action-save').removeClass('is-disabled');
                }
            }

            return this;
        },

        /**
         * Loads the named template from the page, or logs an error if it fails.
         * @param name The name of the template.
         * @returns The loaded template.
         */
        loadTemplate: function(name) {
            var templateSelector = "#" + name,
                templateText = $(templateSelector).text();
            if (!templateText) {
                console.error("Failed to load " + name + " template");
            }
            return _.template(templateText);
        }
    });

    return AbstractEditor;
});
