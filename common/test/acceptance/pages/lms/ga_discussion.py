from .discussion import (
    DiscussionTabHomePage as EdXDiscussionTabHomePage
)


class DiscussionTabHomePage(EdXDiscussionTabHomePage):

    def view_dialog_image_insert(self):
        self.q(css='#wmd-image-button-js-post-body-undefined').first.click()
        self.wait_for_element_visibility('div.image-link-wmd-prompt-dialog', "Prompt dialog visible")
        return self

    def exists_input_file_on_dialog(self):
        return self.q(css='#file-upload-proxy').present
