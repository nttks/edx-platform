define(['Markdown.Editor'], function(MarkdownEditor) {
    'use strict';
    describe('Markdown.Editor', function() {
        var editor = new MarkdownEditor();

        describe('util.isValidUrl', function () {
            it('should return true for http://example.com', function () {
                expect(
                    editor.util.isValidUrl('http://example.com')
                ).toBeTruthy();
            });
            it('should return true for https://example.com', function () {
                expect(
                    editor.util.isValidUrl('https://example.com')
                ).toBeTruthy();
            });
            it('should return true for ftp://example.com', function () {
                expect(
                    editor.util.isValidUrl('ftp://example.com')
                ).toBeTruthy();
            });
            it('should return false for http://', function () {
                expect(editor.util.isValidUrl('http://')).toBeFalsy();
            });
            it('should return false for https://', function () {
                expect(editor.util.isValidUrl('https://')).toBeFalsy();
            });
            it('should return false for ftp://', function () {
                expect(editor.util.isValidUrl('ftp://')).toBeFalsy();
            });
            it('should return false for fake://example.com', function () {
                expect(
                    editor.util.isValidUrl('fakeprotocol://example.com')
                ).toBeFalsy();
            });
            it('should return false for fake://', function () {
                expect(
                    editor.util.isValidUrl('fakeprotocol://')
                ).toBeFalsy();
            });
            it('should return false for www.noprotocol.com', function () {
                expect(
                    editor.util.isValidUrl('www.noprotocol.com')
                ).toBeFalsy();
            });
            it('should return false for an empty string', function () {
                expect(
                    editor.util.isValidUrl('')
                ).toBeFalsy();
            });
        });
        describe('util.checkSize', function () {
            it('should return true for under 4Mbytes', function () {
              expect(
                  editor.util.checkSize([{'size': 4194304}])
              ).toBeTruthy();
            });
            it('should return false for over 4Mbytes', function () {
              expect(
                  editor.util.checkSize([{'size': 4194305}])
              ).toBeFalsy();
            });
            it('should return false for non files', function () {
              expect(
                  editor.util.checkSize([])
              ).toBeFalsy();
            });
        });

        describe('check ui.prompt', function () {
            it('ui.prompt', function () {
                expect(function(){
                    editor.ui.prompt(gettext("Insert Image (Type URL or Select File)"),
                                     gettext("Insert Image (Type URL)"),
                                     gettext("Please provide a valid URL."),
                                     '',
                                     gettext("Description is Required"),
                                     false,
                                     "http://",
                                     ''
                                    )
                  }
                ).not.toThrow();
            });
        });
    });
});
