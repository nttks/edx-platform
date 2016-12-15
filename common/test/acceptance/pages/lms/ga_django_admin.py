"""
Django admin page.
"""

import re

from bok_choy.page_object import PageObject

from . import BASE_URL


KEY_GRID_INDEX = '__index'


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

    def click_list(self, module_name, model_name):
        self.q(css='th[scope="row"]>a[href="/admin/{module_name}/{model_name}/"]'.format(
            module_name=module_name,
            model_name=model_name)).first.click()
        return DjangoAdminListPage(self.browser, module_name, model_name).wait_for_page()


class DjangoAdminGridMixin(object):

    @property
    def grid_columns(self):
        return [el.text.strip() for el in self.q(css='table#result_list>thead>tr>th').results if el.is_displayed()]

    @property
    def grid_rows(self):
        columns = self.grid_columns
        if not columns:
            return []

        all_datas = [el.text.strip() for el in self.q(css='table#result_list>tbody>tr>*').results if el.is_displayed()]

        if len(all_datas) % len(columns) != 0:
            raise ValueError('Data count of all({}) % count of columns({}) not ZERO.'.format(len(all_datas), len(columns)))

        grid_rows = []
        for i, row_datas in enumerate(zip(*[iter(all_datas)] * len(columns))):
            row = dict(zip(columns, row_datas))
            row[KEY_GRID_INDEX] = i
            grid_rows.append(row)

        return grid_rows

    @property
    def last_grid_row(self):
        rows = self.grid_rows
        return rows[-1] if rows else None

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
            print('{}'.format(self.grid_columns))
            print('{}'.format(self.grid_rows))
            print('{}'.format(search_dict))
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
            return self.q(css='ul.messagelist>li.success').visible and self.q(css='div#changelist.module>form#changelist-form>p.paginator').present
        return self.q(css='div#changelist.module>form#changelist-form>p.paginator').present

    def click_grid_anchor(self, grid_row):
        # Just check one pattern, so be care to use.
        grid_anchor = self.q(css='table#result_list>tbody a').nth(grid_row[KEY_GRID_INDEX])
        record_id = grid_anchor.attrs('href')[0].strip('/').split('/')[-1]
        grid_anchor.click()
        return DjangoAdminModifyPage(self.browser, self.module_name, self.model_name, record_id).wait_for_page()


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

    @property
    def error_messages(self):
        return self.q(css='.errorlist>li').text

    def input(self, data):
        for name, value in data.items():
            input_text = self.q(css='input[name="{}"][type="text"]'.format(name))
            if input_text.present:
                input_text.first.fill(value)
                continue
            input_checkbox = self.q(css='input[name="{}"][type="checkbox"]'.format(name))
            if input_checkbox.present:
                input_checkbox_checked = self.q(css='input[name="{}"][type="checkbox"]:checked'.format(name)).present
                if (value and not input_checkbox_checked) or (not value and input_checkbox_checked):
                    input_checkbox.first.click()
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

    def save(self, success=True):
        self.q(css='div.submit-row>input[name="_save"]').first.click()
        return DjangoAdminListPage(self.browser, self.module_name, self.model_name, True).wait_for_page() if success else self


class DjangoAdminModifyPage(DjangoAdminAddPage):

    def __init__(self, browser, module_name, model_name, record_id):
        super(DjangoAdminAddPage, self).__init__(browser)
        self.module_name = module_name
        self.model_name = model_name
        self.record_id = record_id

    @property
    def url(self):
        return '{base}/admin/{module_name}/{model_name}/{record_id}/'.format(
            base=BASE_URL,
            module_name=self.module_name,
            model_name=self.model_name,
            record_id=self.record_id,
        )

    def is_browser_on_page(self):
        return super(DjangoAdminModifyPage, self).is_browser_on_page and self.q(css='div.submit-row>p.deletelink-box>a.deletelink').present

    def click_delete(self):
        self.q(css='div.submit-row>p.deletelink-box>a.deletelink').first.click()
        # Just check one pattern, so be care to use.
        return DjangoAdminDeleteConfirmPage(self.browser, self.module_name, self.model_name, self.record_id).wait_for_page()


class DjangoAdminDeleteConfirmPage(PageObject):

    def __init__(self, browser, module_name, model_name, record_id):
        super(DjangoAdminDeleteConfirmPage, self).__init__(browser)
        self.module_name = module_name
        self.model_name = model_name
        self.record_id = record_id

    @property
    def url(self):
        return '{base}/admin/{module_name}/{model_name}/{record_id}/delete/'.format(
            base=BASE_URL,
            module_name=self.module_name,
            model_name=self.model_name,
            record_id=self.record_id,
        )

    def is_browser_on_page(self):
        return self.q(css='form>div>input[type="submit"]').present and self.q(css='form>div>a.button.cancel-link').present

    def click_yes(self):
        self.q(css='form>div>input[type="submit"]').first.click()
        return DjangoAdminListPage(self.browser, self.module_name, self.model_name, True).wait_for_page()

    def click_back(self):
        self.q(css='form>div>a.button.cancel-link').first.click()
        return DjangoAdminModifyPage(self.browser, self.module_name, self.model_name, self.record_id).wait_for_page()


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
