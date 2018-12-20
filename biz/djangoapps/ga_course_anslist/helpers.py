# -*- coding: utf-8 -*-
import logging
import copy
from string import Template
from collections import OrderedDict

LOG_LEVEL = logging.DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format="[%(asctime)s][%(levelname)s](%(filename)s:%(lineno)s) %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S"
)
log = logging.getLogger(__name__)

GRID_COLUMNS = [
    ["Organization Name","text"],
    #["Group Code", "text"],
    ["Member Code","text"],
    ["Username","text"],
    ["Email","text"],
    ["Full Name", "text"],
    ["Login Code", "text"],
    ["Enroll Date","date"],
    #["Student Status","text"]
]

GRID_COLUMNS_HIDDEN = [
    ["Group Code", "hidden"],
    ["Student Status","hidden"]
]

QUERY_STATEMENT_SURVEY_NAMES = '''
	SELECT 
	    sbm.id
	  , sbm.unit_id
	  , sbm.course_id
	  , sbm.survey_name
	  , min(sbm.created)
	FROM
	  ga_survey_surveysubmission as sbm
	WHERE 1 = 1
	  and sbm.course_id = '$course_id'
    group by sbm.unit_id
	order by sbm.created
'''

def _create_survey_name_list_statement(course_id):
    templ = Template(QUERY_STATEMENT_SURVEY_NAMES)
    sql_statement = templ.substitute(course_id=course_id)
    return sql_statement


QUERY_STATEMENT_USER_NOT_MEMBERS = '''
    SELECT
        enroll.id
      , cntr.contractor_organization_id as org_id
      , det.contract_id
      , enroll.course_id
      , enroll.user_id
      , usr.username
      , usr.email
      , bzusr.login_code
      , prof.name
      , enroll.created
    FROM student_courseenrollment as enroll
    LEFT JOIN ga_contract_contractdetail as det
        ON enroll.course_id = det.course_id
    LEFT JOIN ga_contract_contract as cntr
        ON det.contract_id = cntr.id
    LEFT JOIN ga_organization_organization as org
        ON cntr.contractor_organization_id = org.id
    LEFT JOIN auth_user as usr
        ON enroll.user_id = usr.id
    LEFT JOIN ga_invitation_contractregister as reg
        ON enroll.user_id = reg.user_id
    LEFT JOIN ga_login_bizuser as bzusr
        ON usr.id = bzusr.user_id
    LEFT JOIN auth_userprofile as prof
        ON usr.id = prof.user_id
    WHERE 1=1
    AND org.id = $org_id
    AND enroll.course_id =  '$course_id'
    AND reg.contract_id = $contract_id
    AND usr.id not in ($user_ids)
'''


def _create_users_not_members_statement(org_id, contract_id, course_id, user_ids):
    templ = Template(QUERY_STATEMENT_USER_NOT_MEMBERS)
    str_ids = [str(i) for i in user_ids]
    if str_ids:
        sql_statement = templ.substitute(course_id=course_id, contract_id=contract_id, org_id=org_id, user_ids=','.join(str_ids))
    else:
        sql_statement = templ.substitute(course_id=course_id, contract_id=contract_id, org_id=org_id, user_ids=-1)
    return sql_statement

def _get_grid_columns_base(survey_names_list):
    columns_list = []
    columns_list.extend([(col[0], col[1]) for col in GRID_COLUMNS])
    columns_list.extend([(item[1], 'text') for item in survey_names_list])
    return columns_list

def _get_grid_columns_hidden():
    columns_list = []
    columns_list.extend([(col[0], col[1]) for col in GRID_COLUMNS_HIDDEN])
    return columns_list


def _serialize_post_data(post_data):
    POST_DICT_DATA_INPUT = {
        u'group_id': [u''],
        u'survey_name': [u''],
        u'survey_answered': [u'on'],
        u'survey_not_answered': [u'on'],
    }
    log.debug('post_data_base={}'.format(post_data))

    keys = POST_DICT_DATA_INPUT.keys()
    ret_dct = {}
    for k in keys:
        if k in post_data:
            ret_dct.update({k : post_data[k]})
        else:
            ret_dct.update({k : [u'']})

    for k in keys:
        if type(ret_dct[k]) == type([]):
            pass
        elif type(ret_dct[k]) == type(u''):
            ret_dct[k] = [ u'' + ret_dct[k] ]
        elif type(ret_dct[k]) == type(''):
            ret_dct[k] = [ u'' + ret_dct[k] ]

    return ret_dct


def _serialize_post_data_for_detail(post_data):
    i = 1
    keys = []
    while 'detail_condition_member_name_' + str(i) in post_data:
        keys.append(u'detail_condition_member_name_' + str(i))
        i += 1

    j = 1
    val_keys = []
    while 'detail_condition_member_' + str(j) in post_data:
        val_keys.append(u'detail_condition_member_' + str(j))
        j += 1

    _dct = {}
    for k in keys:
        if type(post_data[k]) == type([]):
            _dct[k] = u'' + post_data[k][0]
        elif type(post_data[k]) == type(u''):
            _dct[k] = u'' + post_data[k]

    ret_dct = OrderedDict()
    for k, val in zip(keys, val_keys):
        if _dct[k] != u'':
            ret_dct.update({ _dct[k] : post_data[val]})

    ret_lst = []
    for k in ret_dct.keys():
        ret_lst.append({'field' : [k], 'value' : ret_dct[k]})

    return ret_lst


def _set_conditions(post_data):
    log.debug('post_data={}'.format(post_data))
    conditions_members = []

    ser_dct = _serialize_post_data(post_data)

    value = ser_dct[u'group_id']
    field = u'group_id'
    conditions_members.append({'field': [field], 'value': value})

    conditions_members += _serialize_post_data_for_detail(post_data)

    condition_survey_name = []

    survey_value = ser_dct[u'survey_name']
    survey_field = [u'survey_name']
    survey_answered = ser_dct[u'survey_answered']
    survey_not_answered = ser_dct[u'survey_not_answered']
    condition_survey_name.append({
        'field': survey_field,
        'value': survey_value,
        'survey_answered': survey_answered,
        'survey_not_answered': survey_not_answered
    })

    return conditions_members, condition_survey_name


def _transform_grid_records(dct_added, conditions=None):
    log.debug('condition={}'.format(conditions))
    if conditions:
        answered = bool(conditions[0]['survey_answered'][0])
        not_answered = bool(conditions[0]['survey_not_answered'][0])

        all_flag = answered and not_answered
        if not (answered or not_answered):
            all_flag = True

        survey_name = conditions[0]['value'][0]
        if not survey_name:
            all_flag = True

    else:
        all_flag = True
        answered = True
        not_answered = True
        survey_name = ''

    grid_records = []
    recid = 0
    users = dct_added.keys()
    for user_id in users:
        if all_flag:
            recid += 1
            dct_added[user_id].update({'recid' : recid, })
            del dct_added[user_id]['obj']
            grid_records.append(copy.deepcopy(dct_added[user_id]))
        else:
            sname = u'' + survey_name
            target_value = dct_added[user_id][sname] if sname in dct_added[user_id] else ''
            log.debug(target_value)
            if answered:
                if target_value:
                    recid += 1
                    dct_added[user_id].update({'recid' : recid, })
                    del dct_added[user_id]['obj']
                    grid_records.append(copy.deepcopy(dct_added[user_id]))
            if not_answered:
                if not target_value:
                    recid += 1
                    dct_added[user_id].update({'recid' : recid, })
                    del dct_added[user_id]['obj']
                    grid_records.append(copy.deepcopy(dct_added[user_id]))

    return grid_records


def _populate_for_tsv(columns, records):
    rows = []
    header = [lst[0] for lst in columns]
    row = []
    for rec in records:
        for col in header:
            val = rec[col] if col in rec else ''
            row.append(val)

        rows.append(copy.deepcopy(row))
        del row[:]

    return header, rows


def _smoke_test(a, b):
    return a + b
