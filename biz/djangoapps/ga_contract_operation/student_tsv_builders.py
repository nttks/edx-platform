# -*- coding: utf-8 -*-
from collections import OrderedDict
from django.utils.translation import ugettext as _
from biz.djangoapps.ga_invitation.models import (
    ContractRegister,
    STATUS as CONTRACT_REGISTER_STATUS,
)
from biz.djangoapps.ga_contract_operation.utils import get_additional_info_by_contract

FIELD_STATUS = 'status'
FIELD_FULL_NAME = 'full_name'
FIELD_GROUP_NAME = 'group_name'
FIELD_CODE = 'code'
FIELD_EMAIL = 'email'
FIELD_LOGIN_CODE = 'login_code'
FIELD_USERNAME = 'username'
FIELD_MEMBER_DELETE = 'is_delete'
FIELD_ORG_NUMBER = 'org'
FIELD_ITEM_NUMBER = 'item'


class ContractRegisterTsv:
    def __init__(self, contract=None):
        """
        :param contract: from biz.djangoapps.ga_contract.models import Contract
        """
        self.contract = contract
        self.org_item_number_list = []

        self.header_columns = OrderedDict()
        self.header_columns[FIELD_STATUS] = _("Student Status")
        self.header_columns[FIELD_FULL_NAME] = _("Full Name")
        self.header_columns[FIELD_GROUP_NAME] = _("Organization Groups")
        self.header_columns[FIELD_CODE] = _("Member Code")
        self.header_columns[FIELD_EMAIL] = _("Email Address")
        self.header_columns[FIELD_LOGIN_CODE] = _("Login Code")
        self.header_columns[FIELD_USERNAME] = _("Username")
        self.header_columns[FIELD_MEMBER_DELETE] = _("Target user of delete member master")
        for i in range(1, 11):
            self.header_columns[FIELD_ORG_NUMBER + str(i)] = _("Organization") + str(i)
            self.org_item_number_list.append(FIELD_ORG_NUMBER + str(i))
        for i in range(1, 11):
            self.header_columns[FIELD_ITEM_NUMBER + str(i)] = _("Item") + str(i)
            self.org_item_number_list.append(FIELD_ITEM_NUMBER + str(i))

    @property
    def headers_for_export(self):
        """
        Get headers rows for file to export
        :return:
        """
        return self.header_columns.values()

    def get_header_and_record_for_export(self, query, prefetch):
        """
        Get header and record rows for file to export.
        :param query: Q()
        :param prefetch: Prefetch()
        :return: headers and columns on tsv file.
        """
        rows = []
        select_columns = dict({
            'user_id': 'user__id',
            FIELD_STATUS: 'status',
            FIELD_FULL_NAME: 'user__profile__name',
            FIELD_EMAIL: 'user__email',
            FIELD_USERNAME: 'user__username',
            FIELD_LOGIN_CODE: 'user__bizuser__login_code',
            FIELD_CODE: 'user__member__code',
            FIELD_MEMBER_DELETE: 'user__member__is_delete',
            FIELD_GROUP_NAME: 'user__member__group__group_name'
        })
        select_columns.update({'org' + str(i): 'user__member__org' + str(i) for i in range(1, 11)})
        select_columns.update({'item' + str(i): 'user__member__item' + str(i) for i in range(1, 11)})

        # Load Data
        user_additional_settings, display_names, __, __ = get_additional_info_by_contract(self.contract)

        # headers and additional info setting names
        headers = self.headers_for_export
        headers.extend(display_names)

        status = dict(CONTRACT_REGISTER_STATUS)

        def _get_row(register):
            row = []
            for column in self.header_columns.keys():
                if column == FIELD_STATUS:
                    row.append(status[register.get(select_columns.get('status'))])
                else:
                    row.append(register.get(
                        select_columns[column]) if register.get(select_columns[column]) is not None else '')

            # additional info settings
            for display_name in display_names:
                user_id = register.get(select_columns.get('user_id'))
                if user_id in user_additional_settings and display_name in user_additional_settings[user_id]:
                    row.append(user_additional_settings[user_id][display_name])

            return row

        if query is not None:
            contract_registers = ContractRegister.objects.filter(
                query).select_related('user__profile', 'user__bizuser', 'user__registration').prefetch_related(
                prefetch).distinct().order_by('id').values(*select_columns.values())

            # headers and additional info setting names
            headers = self.headers_for_export
            headers.extend(display_names)

            # records
            for contract_register in contract_registers:
                rows.append(_get_row(dict(contract_register)))

        return headers, rows
