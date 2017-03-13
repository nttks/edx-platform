"""
Contract operation pages of biz.
"""
from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin, W2uiGrid, KEY_GRID_INDEX


class BizTaskHistoryMixin(object):

    def __init__(self, *args, **kwargs):
        super(BizTaskHistoryMixin, self).__init__()
        self.task_history_grid = W2uiGrid(self, '#task-history-grid.w2ui-grid')

    def click_show_history(self):
        self.q(css='#task-history-btn').click()
        self.wait_for_ajax()
        self.wait_for_element_visibility('#task-history-grid.w2ui-grid', 'Task history grid visible')
        return self

    @property
    def task_history_grid_row(self):
        return self.get_task_history_grid_row(0)

    def get_task_history_grid_row(self, index):
        return self.task_history_grid.get_row({
            KEY_GRID_INDEX: index
        })

    @property
    def task_messages(self):
        return self.get_task_messages(0)

    def get_task_messages(self, index):
        with self.task_history_grid.click_expand(index=index) as expanded_grid:
            return expanded_grid.grid_rows

    def wait_for_task_complete(self):
        def _wait_for():
            self.click_show_history()
            return self.task_history_grid_row['State'] == 'Complete'
        self.wait_for(_wait_for, 'Latest task state is not Complete')


class BizStudentsPage(BizNavPage, BizTaskHistoryMixin, W2uiMixin):
    """
    Students page for unregister and mask
    """

    url = "{base}/biz/contract_operation/students".format(base=BASE_URL)

    def __init__(self, browser):
        super(BizStudentsPage, self).__init__(browser)
        self.student_grid = W2uiGrid(self, '#grid.w2ui-grid')

    def is_browser_on_page(self):
        return self.pagetitle == u'Students List'

    def click_unregister_button(self):
        """
        Click the unregister button
        """
        self.q(css='#unregister-btn').click()
        self.wait_for_ajax()
        return self

    def click_personalinfo_mask_button(self):
        """
        Click the personalinfo mask button
        """
        self.q(css='#personalinfo-mask-btn').click()
        self.wait_for_ajax()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="div.main ul.messages li").text


class BizRegisterStudentsPage(BizNavPage, BizTaskHistoryMixin, W2uiMixin):
    """
    Register students page
    """

    @property
    def url(self):
        return '{base}/biz/contract_operation/register_students'.format(base=BASE_URL)

    def is_browser_on_page(self):
        """
        Check if browser is showing the page.
        """
        return 'Register Students' in self.browser.title

    def input_students(self, value):
        """
        Input students info

        Arguments:
            value : target students
        """
        self.q(css='textarea#list-students').fill(value)
        return self

    def click_register_status(self):
        """
        Click the register status checkbox
        """
        self.q(css='#register-status').click()
        return self

    def click_register_button(self):
        """
        Click the register button
        """
        self.q(css='#register-btn').click()
        self.wait_for_ajax()
        return self

    @property
    def messages(self):
        """Return a list of errors displayed to the list view. """
        return self.q(css="div.main ul.messages li").text
