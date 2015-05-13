"""
Pages for survey
"""
from bok_choy.page_object import PageObject
from bok_choy.promise import Promise


class SurveyPage(PageObject):
    """
    Survey page
    """

    url = None

    def is_browser_on_page(self):
        return self.q(css='form#survey-form').visible

    def fill_item(self, item_id, value):
        """
        Fill in the survey item
        """
        # Text
        if self.q(css=u"div#{0} input[type='text']".format(item_id)).present:
            self.q(css=u"div#{0} input[type='text']".format(item_id)).fill(value)
        # Textarea
        elif self.q(css=u"div#{0} textarea".format(item_id)).present:
            self.q(css=u"div#{0} textarea".format(item_id)).fill(value)
        # Check box
        elif self.q(css=u"div#{0} input[value='{1}']".format(item_id, value)).present:
            self.q(css=u"div#{0} input[value='{1}']".format(item_id, value)).first.click()
        # Select menu
        elif self.q(css=u"div#{0} option[value='{1}']".format(item_id, value)).present:
            self.q(css=u"div#{0} option[value='{1}']".format(item_id, value)).first.click()

    def submit(self):
        """
        Click the submit button
        """
        self.q(css='button#survey-submit-button').click()

    def is_submit_button_enabled(self):
        """
        Return whether the submit button is enabled
        """
        # Note: BrowserQuery.attrs('class') would be like [u'action disabled']
        submit_button_classes = self.q(css='button#survey-submit-button').attrs('class')[0]
        return 'disabled' not in submit_button_classes.split()

    @property
    def messages(self):
        """Return a list of messages displayed to the user. """
        return self.q(css="div.message>div").text

    def wait_for_messages(self):
        """Wait for messages to be visible, then return them. """
        def _check_func():
            """Return success status and any messages that occurred."""
            messages = self.messages
            return (any(messages), messages)
        return Promise(_check_func, "Messages are visible").fulfill()
