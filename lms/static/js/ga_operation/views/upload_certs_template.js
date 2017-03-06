;(function (define) {

    define(['jquery', 'backbone', 'js/ga_operation/views/ga_base'], function ($, Backbone, GaBaseView) {
        'use strict';

        return GaBaseView.extend({
            events:{
                'click #confirm_certs_template': 'confirmCertsTemplate',
                'click #upload_certs_template': 'uploadCertsTemplate'
            },

            confirmCertsTemplate: function(event) {
                this.post(event, 'confirm_certs_template', function(response) {
                    var $certsTemplates = $('#certs_templates'),
                        certsTmpl = _.template('<li><a href="<%= url %>" target="_blank"><%= label %>(<%= name %>)</a></li>');
                    $certsTemplates.empty();
                    if (response.templates && response.templates.length > 0) {
                        _.each(response.templates, function(template) {
                            $certsTemplates.append(certsTmpl(template));
                        });
                    } else {
                        $certsTemplates.append($('<li>').text('テンプレートがアップロードされていません。'));
                    }
                });
            },

            uploadCertsTemplate: function(event) {
                this.post(event, 'upload_certs_template');
            }
        });
    });

})(define || RequireJS.define);
