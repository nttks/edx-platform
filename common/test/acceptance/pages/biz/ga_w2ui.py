"""
Biz mixin for w2ui.
"""
import re
from selenium.webdriver.common.keys import Keys

from bok_choy.javascript import js_defined


KEY_GRID_INDEX = '__index'


def remove_grid_row_index(grid_row):
    if KEY_GRID_INDEX in grid_row:
        grid_row.pop(KEY_GRID_INDEX)
    return grid_row


class W2uiMixin(object):

    @property
    def grid_columns(self):
        return [el.text.strip() for el in self.q(css='td.w2ui-head>div.w2ui-col-header').results if el.is_displayed()]

    @property
    def grid_rows(self):
        columns = self.grid_columns
        all_datas = [el.text.strip() for el in self.q(css='td.w2ui-grid-data>div').results if el.is_displayed()]

        if len(all_datas) % len(columns) != 0:
            raise ValueError('Data count of all({}) % count of columns({}) not ZERO.'.format(len(all_datas), len(columns)))

        grid_rows = []
        for i, row_datas in enumerate(zip(*[iter(all_datas)] * len(columns))):
            row = dict(zip(columns, row_datas))
            row[KEY_GRID_INDEX] = i
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

    def click_grid_row(self, search_dict, cls_next_page=None):
        anchor = self.q(css='td.w2ui-grid-data>div>a').nth(self.get_row(search_dict)['__index'])
        anchor_href = anchor.attrs('href')[0]
        anchor.click()

        return cls_next_page(self.browser, href=anchor_href).wait_for_page() if cls_next_page else self

    def wait_for_popup_enable(self):
        self.wait_for_element_visibility('div#w2ui-popup', 'W2ui popup is visible')
        # wait for animation of w2ui popup
        self.wait_for(
            lambda: 'transform' not in re.split(r'[\s;:]', self.q(css='div#w2ui-popup').first.attrs('style')[0]),
            'W2ui popup is transformed')
        return self

    def wait_for_lock_absence(self):
        self.wait_for_element_absence('div.w2ui-lock,div.w2ui-lock-msg', 'W2ui lock is absence')
        return self

    def wait_for_popup_absence(self):
        self.wait_for_element_absence('div#w2ui-popup', 'W2ui popup is absence')
        return self

    def click_popup_yes(self, cls_next_page=None):
        self.wait_for_popup_enable()
        self.q(css='div#w2ui-popup>div.w2ui-msg-buttons>button#Yes').first.click()
        return cls_next_page(self.browser).wait_for_page() if cls_next_page else self.wait_for_popup_absence()

    def click_popup_no(self, cls_next_page=None):
        self.wait_for_popup_enable()
        self.q(css='div#w2ui-popup>div.w2ui-msg-buttons>button#No').first.click()
        return cls_next_page(self.browser).wait_for_page() if cls_next_page else self.wait_for_popup_absence()

    def click_grid_icon_columns(self):
        self.q(css='table.w2ui-button').first.click()
        self.wait_for_overlay_visibility()
        self.wait_for_element_visibility('div.w2ui-col-on-off', 'W2ui column on/off is visible')
        return self

    def wait_for_overlay_visibility(self):
        self.wait_for_element_visibility('div.w2ui-overlay', 'W2ui overlay is visible')

        # wait for opacity of w2ui overlay
        self.wait_for(
            lambda: 'opacity' not in re.split(r'[\s;:]', self.q(css='div.w2ui-overlay').first.attrs('style')[0]),
            'W2ui overlay has no opacity')

        # Style left of overlay is minus value(ex. -82px).
        # So set zero value(0px). Why dont know!!
        @js_defined('window.jQuery')
        def _adjust_overlay():
            self.browser.execute_script("""
                jQuery('div.w2ui-overlay').css('left', '0px');
            """)

        _adjust_overlay()
        return self

    def wait_for_overlay_absence(self):
        self.wait_for_element_absence('div#w2ui-overlay', 'W2ui overlay is absence')
        return self

    @property
    def grid_icon_columns(self):
        return self.q(css='div.w2ui-col-on-off td>label').text

    def is_checked_grid_icon_columns(self, label_name):
        index = self._index_of_grid_icon_columns(label_name)
        return self.q(css='div.w2ui-col-on-off td>input').nth(index).selected

    def click_grid_icon_columns_checkbox(self, label_name):
        index = self._index_of_grid_icon_columns(label_name)
        self.q(css='div.w2ui-col-on-off td>input').nth(index).first.click()
        return self

    def _index_of_grid_icon_columns(self, label_name):
        grid_icon_columns = self.grid_icon_columns
        for i, name in enumerate(grid_icon_columns):
            if name == label_name:
                return i
        raise ValueError('Not found label({}) in grid-icon-columns({})'.format(label_name, grid_icon_columns))

    def click_grid_icon_columns_label(self, label_name):
        index = self._index_of_grid_icon_columns(label_name)
        self.q(css='div.w2ui-col-on-off td>label').nth(index).first.click()
        return self.wait_for_overlay_absence()

    def click_grid_icon_search(self):
        self.q(css='div.w2ui-icon.w2ui-search-down').first.click()
        self.wait_for_overlay_visibility()
        self.wait_for_element_visibility('div.w2ui-select-field', 'W2ui select field is visible')
        return self

    @property
    def grid_icon_search(self):
        return [el.text.strip() for el in self.q(css='div.w2ui-select-field>table>tbody>tr>td:nth-of-type(2)').results if el.is_displayed()]

    def _index_of_grid_icon_search(self, label_name):
        grid_icon_search = self.grid_icon_search
        for i, name in enumerate(grid_icon_search):
            if name == label_name:
                return i
        raise ValueError('Not found label({}) in grid-icon-search({})'.format(label_name, grid_icon_search))

    def is_checked_grid_icon_search(self, label_name):
        index = self._index_of_grid_icon_search(label_name)
        return self.q(css='div.w2ui-select-field>table>tbody>tr>td:nth-of-type(1)>input').nth(index).selected

    def click_grid_icon_search_label(self, label_name):
        index = self._index_of_grid_icon_search(label_name)
        self.q(css='div.w2ui-select-field>table>tbody>tr').nth(index).first.click()
        return self.wait_for_overlay_absence()

    @property
    def search_placeholder(self):
        return self.q(css='input.w2ui-search-all').attrs('placeholder')[0].strip()

    def search(self, search_text=''):
        search_field = self.q(css='input.w2ui-search-all')
        search_field.fill(search_text)
        search_field.first[0].send_keys(Keys.RETURN)
        return self

    def click_search(self):
        self.q(css='input.w2ui-search-all').first.click()
        return self

    def clear_search(self):
        self.q(css='div.w2ui-search-clear').first.click()
        return self

    def wait_for_calendar_visibility(self):
        self.wait_for_overlay_visibility()
        self.wait_for_element_visibility('div.w2ui-overlay div.w2ui-calendar>div.w2ui-calendar-title', 'W2ui calendar is visible')
        return self

    @property
    def calendar_date(self):
        return self.q(css='td.w2ui-date').attrs('date')

    def click_calendar(self, date_yyyy_mm_dd):
        self.q(css='td.w2ui-date[date="{}"]'.format(date_yyyy_mm_dd)).first.click()
        return self

    def click_calendar_prev(self):
        self.q(css='div.w2ui-calendar-title>div.w2ui-calendar-previous').first.click()
        return self

    def click_calendar_next(self):
        self.q(css='div.w2ui-calendar-title>div.w2ui-calendar-next').first.click()
        return self

    def click_calendar_title(self):
        self.q(css='div.w2ui-calendar-title').first.click()
        self.wait_for_element_visibility('div.w2ui-calendar-title+div.w2ui-calendar-jump', 'W2ui calendar jump is visible')
        return self

    def click_calendar_jump(self, year, month):
        self.q(css='div.w2ui-jump-year[name="{}"]'.format(year)).first.click()
        # month of args: 1-12
        # w2ui 0:January, 11:December
        self.q(css='div.w2ui-jump-month[name="{}"]'.format(month - 1)).first.click()
        self.wait_for_element_absence('div.w2ui-calendar-title+div.w2ui-calendar-jump', 'W2ui calendar jump is absence')
        return self

    def click_sort(self, column_name):
        self.q(css='td.w2ui-head').nth(self.grid_columns.index(column_name)).first.click()
        return self
