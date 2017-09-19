define(['Markdown.Sanitizer'], function(MarkdownSanitizer) {
    'use strict';
    describe('Markdown.sanitizer', function() {

        describe('sanitizer.sanitizeHtml', function () {
            it('should return Equal for http://example.com', function () {
                expect(function(){
                    MarkdownSanitizer.sanitizeHtml('<a href=\"https://example.com\" target=\"_blank\"><img src=\"https://example.com\" alt=\"aaa\" title=\"\" class=\"discussion-image\"> </a>')
                }
              ).not.toEqual('<a href=\"https://example.com\" target=\"_blank\"><img src=\"https://example.com\" alt=\"aaa\" title=\"\" class=\"discussion-image\"> </a>');
            });
        });
    });
});
