# -*- coding: utf-8 -*-
from collections import OrderedDict
from django.utils.translation import ugettext as _
from biz.djangoapps.gx_member.models import Member

FIELD_GROUP_CODE = 'group_code'
FIELD_CODE = 'code'
FIELD_EMAIL = 'email'
FIELD_FIRST_NAME = 'first_name'
FIELD_LAST_NAME = 'last_name'
FIELD_PASSWORD = 'password'
FIELD_USERNAME = 'username'
FIELD_LOGIN_CODE = 'login_code'
FIELD_ORG_NUMBER = 'org'
FIELD_ITEM_NUMBER = 'item'


class MemberTsv:
    def __init__(self, org=None):
        """
        :param org: from biz.djangoapps.ga_organization.models import Organization
        """
        self.org = org

        self.header_columns = OrderedDict()
        self.header_columns[FIELD_GROUP_CODE] = _("Organization Code")
        self.header_columns[FIELD_CODE] = _("Member Code")
        self.header_columns[FIELD_EMAIL] = _("Email Address")
        self.header_columns[FIELD_FIRST_NAME] = _("Last Name")
        self.header_columns[FIELD_LAST_NAME] = _("First Name")
        self.header_columns[FIELD_PASSWORD] = _("Password")
        self.header_columns[FIELD_USERNAME] = _("Username")
        self.header_columns[FIELD_LOGIN_CODE] = _("Login Code")
        for i in range(1, 11):
            self.header_columns[FIELD_ORG_NUMBER + str(i)] = _("Organization") + str(i)
        for i in range(1, 11):
            self.header_columns[FIELD_ITEM_NUMBER + str(i)] = _("Item") + str(i)

    @property
    def headers_for_export(self):
        """
        Get headers rows for file to export
        :return:
        """
        return self.header_columns.values()

    @property
    def headers_for_import(self):
        """
        Get headers for file import
        :return:
        """
        return self.header_columns.keys()

    def _load_data(self):
        data = Member.objects.filter(org=self.org, is_active=True, is_delete=False).select_related(
            'user', 'user__bizuser', 'group').order_by('group__level_no', 'group__group_code', 'code')
        return data

    def get_rows_for_export(self):
        """
        Get record rows for file to export.
        :return:
        """
        rows = []
        for data in self._load_data():
            row = []
            group = getattr(data, 'group', None)
            user = getattr(data, 'user')
            bizuser = getattr(user, 'bizuser', None)
            for column in self.header_columns.keys():
                if column is FIELD_GROUP_CODE:
                    row.append(group.group_code if group else '')
                elif column is FIELD_EMAIL:
                    row.append(user.email)
                elif column is FIELD_FIRST_NAME:
                    row.append(user.first_name)
                elif column is FIELD_LAST_NAME:
                    row.append(user.last_name)
                elif column is FIELD_USERNAME:
                    row.append(user.username)
                elif column is FIELD_PASSWORD:
                    row.append('')
                elif column is FIELD_LOGIN_CODE:
                    row.append(bizuser.login_code if bizuser else '')
                else:
                    row.append(getattr(data, column))
            rows.append(row)
        return rows

    def get_dic_by_import_row(self, row):
        """
        Get dictionary object by row of import file.
        :param row:
        :return:
        """
        return {
            column: row[i] for i, column in enumerate(self.headers_for_import)
        }
