define(['Markdown.Converter'], function(MarkdownConverter) {
    'use strict';
    describe('Markdown.converter', function() {
        var converter = new MarkdownConverter();

        describe('nverter.makeHtml', function () {
            it('should return non error for http://example.com', function () {
                expect(function(){
                    converter.makeHtml('![aaa][1]\n  [1]: https://example.com')
                }
              ).not.toBeNull();
            });
        });
    });
});
