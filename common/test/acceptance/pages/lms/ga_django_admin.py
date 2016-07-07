"""
Django admin page.
"""

import re

from bok_choy.page_object import PageObject

from . import BASE_URL


class DjangoAdminPage(PageObject):
    """
    Django admin, where the staff can add/update
    database records.
    """
    url = "{base}/admin".format(base=BASE_URL)

    def is_browser_on_page(self):
        return self.q(css='h1#site-name').present

    def click_add(self, module_name, model_name):
        self.q(css='.addlink[href="/admin/{module_name}/{model_name}/add/"]'.format(
            module_name=module_name,
            model_name=model_name)).first.click()
        return DjangoAdminAddPage(self.browser, module_name, model_name).wait_for_page()


class DjangoAdminGridMixin(object):

    @property
    def grid_columns(self):
        return [el.text.strip() for el in self.q(css='table#result_list>thead>tr>th').results if el.is_displayed()]

    @property
    def grid_rows(self):
        columns = self.grid_columns
        all_datas = [el.text.strip() for el in self.q(css='table#result_list>tbody>tr>*').results if el.is_displayed()]

        if len(all_datas) % len(columns) != 0:
            raise ValueError('Data count of all({}) % count of columns({}) not ZERO.'.format(len(all_datas), len(columns)))

        grid_rows = []
        for i, row_datas in enumerate(zip(*[iter(all_datas)] * len(columns))):
            row = dict(zip(columns, row_datas))
            row['__index'] = i
            grid_rows.append(row)

        return grid_rows

    def find_rows(self, search_dict):
        return [row for row in self.grid_rows
            if all([
                k in row.keys() and row[k] == v for k, v in search_dict.items()
            ])
        ]

    def get_row(self, search_dict):
        find_rows = self.find_rows(search_dict)
        count_row = len(find_rows)
        if count_row == 1:
            return find_rows[0]
        elif count_row == 0:
            return None
        else:
            raise ValueError('Get row found multiple({}) rows.'.format(count_row))


class DjangoAdminListPage(PageObject, DjangoAdminGridMixin):

    def __init__(self, browser, module_name, model_name, message=False):
        super(DjangoAdminListPage, self).__init__(browser)
        self.module_name = module_name
        self.model_name = model_name
        self.message = message

    @property
    def url(self):
        return '{base}/admin/{module_name}/{model_name}/'.format(
            base=BASE_URL,
            module_name=self.module_name,
            model_name=self.model_name,
        )

    def is_browser_on_page(self):
        if self.message:
            return self.q(css='ul.messagelist>li.info').visible and self.q(css='table#result_list').present
        return self.q(css='table#result_list').present


class DjangoAdminAddPage(PageObject):

    def __init__(self, browser, module_name, model_name):
        super(DjangoAdminAddPage, self).__init__(browser)
        self.module_name = module_name
        self.model_name = model_name

    @property
    def url(self):
        return '{base}/admin/{module_name}/{model_name}/add/'.format(
            base=BASE_URL,
            module_name=self.module_name,
            model_name=self.model_name,
        )

    def is_browser_on_page(self):
        return self.q(css='div.submit-row>input[name="_save"]').present

    def input(self, data):
        for name, value in data.items():
            input_name = self.q(css='input[name="{}"]'.format(name))
            if input_name.present:
                input_name.first.fill(value)
                continue
            select_option_value = self.q(css='select[name="{}"]>option[value="{}"]'.format(name, value))
            if select_option_value.present:
                select_option_value.first.click()
                continue
            select_option_text = self.q(css='select[name="{}"]>option'.format(name)).filter(lambda el: value == el.text.strip())
            if select_option_text.present:
                select_option_text.first.click()
                continue
            raise ValueError('Not found element of {} ({})'.format(name, value))
        return self

    def lookup_user(self, lookup_id, search_word, result_index=0):
        self.q(css='#{}'.format(lookup_id)).first.click()
        self.browser.switch_to_window(self.browser.window_handles[1])
        DjangoAdminLookupUserPage(self.browser).wait_for_page().search(search_word).click_result(result_index)
        self.browser.switch_to_window(self.browser.window_handles[0])
        return self

    def save(self):
        self.q(css='div.submit-row>input[name="_save"]').first.click()
        return DjangoAdminListPage(self.browser, self.module_name, self.model_name, True).wait_for_page()


class DjangoAdminLookupUserPage(PageObject, DjangoAdminGridMixin):

    def __init__(self, browser, word=None):
        super(DjangoAdminLookupUserPage, self).__init__(browser)
        self.word = word

    @property
    def url(self):
        query = ''
        if self.word:
            query = 'q={}&'.format(self.word)
        return '{base}/admin/auth/user/?{query}t=id&pop=1'.format(
            base=BASE_URL,
            query=query,
        )

    def is_browser_on_page(self):
        return self.q(css='form#changelist-search').present

    def search(self, word):
        self.q(css='input#searchbar').first.fill(word)
        self.q(css='form#changelist-search>div>input[type="submit"]').first.click()
        return DjangoAdminLookupUserPage(self.browser, word).wait_for_page()

    def click_result(self, index=0):
        grid_rows = self.grid_rows
        if index >= len(grid_rows):
            raise IndexError('Illegal index={}, grid row length={}'.format(index, len(grid_rows)))
        self.q(css='table#result_list>tbody>tr>th>a').nth(index).click()