"""
Biz mixin for w2ui.
"""
import re


class W2uiMixin(object):

    @property
    def grid_columns(self):
        return [el.text.strip() for el in self.q(css='div.w2ui-col-header').results if el.is_displayed()]

    @property
    def grid_rows(self):
        columns = self.grid_columns
        all_datas = [el.text.strip() for el in self.q(css='td.w2ui-grid-data>div').results if el.is_displayed()]

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
