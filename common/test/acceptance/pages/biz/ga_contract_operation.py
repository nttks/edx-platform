"""
Contract operation pages of biz.
"""

from . import BASE_URL
from .ga_navigation import BizNavPage
from .ga_w2ui import W2uiMixin


class BizStudentsPage(BizNavPage, W2uiMixin):

    url = "{base}/biz/contract_operation/students".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.pagetitle == u'Students List'
