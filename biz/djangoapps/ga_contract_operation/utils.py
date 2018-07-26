from collections import defaultdict

from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting


def get_additional_info_by_contract(contract):
    """
    :param contract:
    :return user_additional_settings: Additional settings value of user.
                                       key:user_id, value:dict{key:display_name, value:additional_settings_value}
             display_names: Display name list of additional settings on contract
             additional_searches: Additional settings list for w2ui
             additional_columns: Additional settings list for w2ui
    """
    additional_searches = []
    additional_columns = []

    additional_info_list = contract.additional_info.all()
    user_additional_settings = defaultdict(dict)
    display_names = []
    if bool(additional_info_list):
        for additional_info in additional_info_list:
            additional_searches.append({
                'field': additional_info.display_name,
                'caption': additional_info.display_name,
                'type': 'text',
            })
            additional_columns.append({
                'field': additional_info.display_name,
                'caption': additional_info.display_name,
                'sortable': True,
                'hidden': True,
                'size': 1,
            })
            display_names.append(additional_info.display_name)

        for setting in AdditionalInfoSetting.find_by_contract(contract):
            if setting.display_name in display_names:
                user_additional_settings[setting.user_id][setting.display_name] = setting.value

    return user_additional_settings, display_names, additional_searches, additional_columns