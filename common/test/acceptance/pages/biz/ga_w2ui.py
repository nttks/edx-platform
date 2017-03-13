"""
Biz mixin for w2ui.
"""
from contextlib import contextmanager
import re
from retrying import retry
from selenium.webdriver.common.keys import Keys

from bok_choy.javascript import js_defined


KEY_GRID_INDEX = '__index'


def remove_grid_row_index(grid_row):
    if KEY_GRID_INDEX in grid_row:
        grid_row.pop(KEY_GRID_INDEX)
    return grid_row


class W2uiGrid(object):

    def __init__(self, page_object, parent_css=None):
        self.page_object = page_object
        self.parent_css = parent_css + ' ' if parent_css else ''

    @property
    def grid_columns(self):
        return [
            el.text.strip()
            for el in self.page_object.q(css='{}td.w2ui-head'.format(self.parent_css)).results
            if el.is_displayed() and 'w2ui-head-last' not in el.get_attribute('class')
        ]

    @property
    def grid_rows(self):
        columns = self.grid_columns
        all_datas = [el.text.strip() for el in self.page_object.q(css='{}td.w2ui-grid-data>div'.format(self.parent_css)).results if el.is_displayed()]

        if not columns:
            return all_datas

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
        anchor = self.page_object.q(css='{}td.w2ui-grid-data>div>a'.format(self.parent_css)).nth(self.get_row(search_dict)[KEY_GRID_INDEX])
        anchor_href = anchor.attrs('href')[0]
        anchor.click()

        return cls_next_page(self.page_object.browser, href=anchor_href).wait_for_page() if cls_next_page else self.page_object

    def click_grid_row_checkbox(self, search_dict):
        checkbox = self.page_object.q(css='{}td.w2ui-grid-data>div>input[type=checkbox]'.format(self.parent_css)).nth(self.get_row(search_dict)[KEY_GRID_INDEX])
        prev_flag = checkbox.selected
        checkbox.click()
        self.page_object.wait_for(
            lambda: prev_flag != checkbox.selected,
            'Checkbox is not clicked'
        )
        return self.page_object

    def wait_for_popup_enable(self):
        self.wait_for_element_visibility('div#w2ui-popup', 'W2ui popup is visible')
        # wait for animation of w2ui popup
        self.page_object.wait_for(
            lambda: 'transform' not in re.split(r'[\s;:]', self.page_object.q(css='div#w2ui-popup').first.attrs('style')[0]),
            'W2ui popup is transformed')
        return self.page_object

    def wait_for_lock_absence(self):
        self.page_object.wait_for_element_absence('div.w2ui-lock,div.w2ui-lock-msg', 'W2ui lock is absence')
        return self.page_object

    def wait_for_popup_absence(self):
        self.page_object.wait_for_element_absence('div#w2ui-popup', 'W2ui popup is absence')
        return self.page_object

    @retry
    def click_popup_yes(self, cls_next_page=None):
        self.wait_for_popup_enable()
        self.page_object.q(css='div#w2ui-popup>div.w2ui-msg-buttons>button#Yes').first.click()
        return cls_next_page(self.page_object.browser).wait_for_page() if cls_next_page else self.page_object.wait_for_popup_absence()

    @retry
    def click_popup_no(self, cls_next_page=None):
        self.wait_for_popup_enable()
        self.page_object.q(css='div#w2ui-popup>div.w2ui-msg-buttons>button#No').first.click()
        return cls_next_page(self.page_object.browser).wait_for_page() if cls_next_page else self.page_object.wait_for_popup_absence()

    def click_grid_icon_columns(self):
        self.page_object.q(css='{}table.w2ui-button'.format(self.parent_css)).first.click()
        self.wait_for_overlay_visibility()
        self.page_object.wait_for_element_visibility('div.w2ui-col-on-off', 'W2ui column on/off is visible')
        return self.page_object

    def wait_for_overlay_visibility(self):
        self.page_object.wait_for_element_visibility('div.w2ui-overlay', 'W2ui overlay is visible')

        # wait for opacity of w2ui overlay
        self.page_object.wait_for(
            lambda: 'opacity' not in re.split(r'[\s;:]', self.page_object.q(css='div.w2ui-overlay').first.attrs('style')[0]),
            'W2ui overlay has no opacity')

        # Style left of overlay is minus value(ex. -82px).
        # So set zero value(0px). Why dont know!!
        @js_defined('window.jQuery')
        def _adjust_overlay():
            self.page_object.browser.execute_script("""
                jQuery('div.w2ui-overlay').css('left', '0px');
            """)

        _adjust_overlay()
        return self.page_object

    def wait_for_overlay_absence(self):
        self.page_object.wait_for_element_absence('div#w2ui-overlay', 'W2ui overlay is absence')
        return self.page_object

    @property
    def grid_icon_columns(self):
        return self.page_object.q(css='div.w2ui-col-on-off td>label').text

    def is_checked_grid_icon_columns(self, label_name):
        index = self._index_of_grid_icon_columns(label_name)
        return self.page_object.q(css='div.w2ui-col-on-off td>input').nth(index).selected

    def click_grid_icon_columns_checkbox(self, label_name):
        index = self._index_of_grid_icon_columns(label_name)
        self.page_object.q(css='div.w2ui-col-on-off td>input').nth(index).first.click()
        return self.page_object

    def _index_of_grid_icon_columns(self, label_name):
        grid_icon_columns = self.grid_icon_columns
        for i, name in enumerate(grid_icon_columns):
            if name == label_name:
                return i
        raise ValueError('Not found label({}) in grid-icon-columns({})'.format(label_name, grid_icon_columns))

    def click_grid_icon_columns_label(self, label_name):
        index = self._index_of_grid_icon_columns(label_name)
        self.page_object.q(css='div.w2ui-col-on-off td>label').nth(index).first.click()
        return self.wait_for_overlay_absence()

    def click_grid_icon_search(self):
        self.page_object.q(css='{}div.w2ui-icon.w2ui-search-down'.format(self.parent_css)).first.click()
        self.wait_for_overlay_visibility()
        self.page_object.wait_for_element_visibility('div.w2ui-select-field', 'W2ui select field is visible')
        return self.page_object

    @property
    def grid_icon_search(self):
        return [el.text.strip() for el in self.page_object.q(css='div.w2ui-select-field>table>tbody>tr>td:nth-of-type(2)').results if el.is_displayed()]

    def _index_of_grid_icon_search(self, label_name):
        grid_icon_search = self.grid_icon_search
        for i, name in enumerate(grid_icon_search):
            if name == label_name:
                return i
        raise ValueError('Not found label({}) in grid-icon-search({})'.format(label_name, grid_icon_search))

    def is_checked_grid_icon_search(self, label_name):
        index = self._index_of_grid_icon_search(label_name)
        return self.page_object.q(css='div.w2ui-select-field>table>tbody>tr>td:nth-of-type(1)>input').nth(index).selected

    def click_grid_icon_search_label(self, label_name):
        index = self._index_of_grid_icon_search(label_name)
        self.page_object.q(css='div.w2ui-select-field>table>tbody>tr').nth(index).first.click()
        return self.wait_for_overlay_absence()

    @property
    def search_placeholder(self):
        return self.page_object.q(css='{}input.w2ui-search-all'.format(self.parent_css)).attrs('placeholder')[0].strip()

    def search(self, search_text=''):
        search_field = self.page_object.q(css='{}input.w2ui-search-all'.format(self.parent_css))
        search_field.fill(search_text)
        search_field.first[0].send_keys(Keys.RETURN)
        return self.page_object

    def click_search(self):
        self.page_object.q(css='{}input.w2ui-search-all'.format(self.parent_css)).first.click()
        return self.page_object

    def clear_search(self):
        self.page_object.q(css='{}div.w2ui-search-clear'.format(self.parent_css)).first.click()
        return self.page_object

    def wait_for_calendar_visibility(self):
        self.wait_for_overlay_visibility()
        self.page_object.wait_for_element_visibility('div.w2ui-overlay div.w2ui-calendar>div.w2ui-calendar-title', 'W2ui calendar is visible')
        return self.page_object

    @property
    def calendar_date(self):
        return self.page_object.q(css='td.w2ui-date').attrs('date')

    def click_calendar(self, date_yyyy_mm_dd):
        self.page_object.q(css='td.w2ui-date[date="{}"]'.format(date_yyyy_mm_dd)).first.click()
        return self.page_object

    def click_calendar_prev(self):
        self.page_object.q(css='div.w2ui-calendar-title>div.w2ui-calendar-previous').first.click()
        return self.page_object

    def click_calendar_next(self):
        self.page_object.q(css='div.w2ui-calendar-title>div.w2ui-calendar-next').first.click()
        return self.page_object

    def click_calendar_title(self):
        self.page_object.q(css='div.w2ui-calendar-title').first.click()
        self.page_object.wait_for_element_visibility('div.w2ui-calendar-title+div.w2ui-calendar-jump', 'W2ui calendar jump is visible')
        return self.page_object

    def click_calendar_jump(self, year, month):
        self.page_object.q(css='div.w2ui-jump-year[name="{}"]'.format(year)).first.click()
        # month of args: 1-12
        # w2ui 0:January, 11:December
        self.page_object.q(css='div.w2ui-jump-month[name="{}"]'.format(month - 1)).first.click()
        self.page_object.wait_for_element_absence('div.w2ui-calendar-title+div.w2ui-calendar-jump', 'W2ui calendar jump is absence')
        return self.page_object

    def click_sort(self, column_name):
        self.page_object.q(css='{}td.w2ui-head'.format(self.parent_css)).nth(self.grid_columns.index(column_name)).first.click()
        return self.page_object

    @retry
    def _find_expanded_grid(self, index):
        expanded_ids = self.page_object.q(css='{}tr.w2ui-expanded-row div.w2ui-grid '.format(self.parent_css)).attrs('id')
        find_suffix = '_rec_{}_expanded'.format(index + 1)
        for expanded_id in expanded_ids:
            if expanded_id.endswith(find_suffix):
                return W2uiGrid(self.page_object, '#{}.w2ui-grid'.format(expanded_id))
        raise Exception('Not found expanded grid, id suffix:{}, ids:{}'.format(find_suffix, expanded_ids))

    @contextmanager
    def click_expand(self, search_dict=None, index=None):
        css_value = '{}td.w2ui-col-expand>div'.format(self.parent_css)
        if index is None:
            index = self.get_row(search_dict)[KEY_GRID_INDEX]
        expand_text = self.page_object.q(css=css_value).nth(index).first.text[0]
        if expand_text == u'+':
            self.page_object.q(css=css_value).nth(index).first.click()
            self.page_object.wait_for(
                lambda: u'+' != self.page_object.q(css=css_value).nth(index).first.text[0],
                'Grid is expanded')

        yield self._find_expanded_grid(index)

        self.page_object.q(css=css_value).nth(index).first.click()
        self.page_object.wait_for(
            lambda: u'+' == self.page_object.q(css=css_value).nth(index).first.text[0],
            'Grid is contracted')


class W2uiMixin(W2uiGrid):

    def __init__(self, *args, **kwargs):
        super(W2uiMixin, self).__init__(self)
