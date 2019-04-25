# -*- coding: utf-8 -*-
import logging
import copy

from django.utils.translation import ugettext as _

from collections import OrderedDict
from lms.djangoapps.courseware.courses import get_course
from student.models import CourseEnrollment
from string import Template
from util.ga_attendance_status import AttendanceStatusExecutor

LOG_LEVEL = logging.DEBUG
logging.basicConfig(
    level=LOG_LEVEL,
    format="[%(asctime)s][%(levelname)s](%(filename)s:%(lineno)s) %(message)s",
    datefmt="%Y/%m/%d %H:%M:%S"
)
log = logging.getLogger(__name__)

GRID_COLUMNS = [
    ["Organization Name", "text"],
    ["Member Code", "text"],
    ["Username", "text"],
    ["Email", "text"],
    ["Full Name", "text"],
    ["Login Code", "text"],
    ["Student Status","text"],
    ["Enroll Date", "date"],
]

GRID_COLUMNS_NON_STATUS = [
    ["Organization Name", "text"],
    ["Member Code", "text"],
    ["Username", "text"],
    ["Email", "text"],
    ["Full Name", "text"],
    ["Login Code", "text"],
    ["Enroll Date", "date"],
]

GRID_COLUMNS_HIDDEN = [
    ["Group Code", "hidden"],
    # ["Student Status","hidden"]
]

QUERY_STATEMENT_SURVEY_NAMES = '''
    SELECT 
            sbm2.id
          , sbm2.unit_id
          , sbm2.course_id
          , sbm2.survey_name
          , sbm2.created
    FROM
        (SELECT 
            sbm.unit_id
          , min(sbm.created) AS created_min
        FROM
          ga_survey_surveysubmission as sbm
        WHERE 1 = 1
        and sbm.course_id = '$course_id'
        group by sbm.unit_id, sbm.course_id
        ) AS min_data
        INNER JOIN ga_survey_surveysubmission sbm2
        ON min_data.unit_id = sbm2.unit_id
        AND min_data.created_min = sbm2.created
        '''

QUERY_STATEMENT_SURVEY_NAMES_MAX = '''
    SELECT 
            sbm2.id
          , sbm2.unit_id
          , sbm2.course_id
          , sbm2.survey_name
          , sbm2.created
    FROM
        (SELECT 
            sbm.unit_id
          , max(sbm.created) AS created_max
        FROM
          ga_survey_surveysubmission as sbm
        WHERE 1 = 1
        and sbm.course_id = '$course_id'
        group by sbm.unit_id, sbm.course_id
        ) AS max_data
        INNER JOIN ga_survey_surveysubmission sbm2
        ON max_data.unit_id = sbm2.unit_id
        AND max_data.created_max = sbm2.created
        '''


def _create_survey_name_list_statement(course_id, flg_get_updated_survey_name=False):
    if flg_get_updated_survey_name:
        templ = Template(QUERY_STATEMENT_SURVEY_NAMES_MAX)
        sql_statement = templ.substitute(course_id=course_id)
    else:
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
    AND reg.contract_id = det.contract_id
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


def _get_grid_columns_base(course_id, survey_names_list):
    columns_list = []
    course = get_course(course_id)
    if course.is_status_managed:
        columns_list.extend([(col[0], col[1]) for col in GRID_COLUMNS])
    else:
        columns_list.extend([(col[0], col[1]) for col in GRID_COLUMNS_NON_STATUS])
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
        ret_lst.append({'field' : [k], 'value': ret_dct[k]})

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


def _transform_grid_records(course_id, dct_added, conditions=None):
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

    enrollment_attribute_dict = {}
    course = get_course(course_id)
    if course.is_status_managed:
        enrollment_attribute_dict = _set_attribute_value(course)

    grid_records = []
    recid = 0
    users = dct_added.keys()
    for user_id in users:
        if course.is_status_managed:
            dct_added[user_id] = _set_student_status_record(dct_added[user_id], enrollment_attribute_dict, user_id)
        if all_flag:
            recid += 1
            dct_added[user_id].update({'recid': recid, })
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


def _set_attribute_value(course):
    enrollment_ids = []
    enroll_dict = {}
    enrollment_attribute_dict = {}
    for enrollment in CourseEnrollment.objects.filter(course_id=course.id).values('id', 'user__id'):
        if enrollment_ids.count(enrollment['id']) is 0:
            enrollment_ids.append(enrollment['id'])
            enroll_dict[enrollment['id']] = enrollment['user__id']
    if enrollment_ids:
        enrollment_attribute = AttendanceStatusExecutor.get_attendance_values(enrollment_ids)
        for enrollment_id, enrollment_user_id in enroll_dict.items():
            if enrollment_id in enrollment_attribute:
                enrollment_attribute_dict[enrollment_user_id] = enrollment_attribute[enrollment_id]

    return enrollment_attribute_dict


def _set_student_status_record(record, attr_dict, user_id):
    if user_id in attr_dict:
        if AttendanceStatusExecutor.attendance_status_is_completed(attr_dict[user_id]):
            record[_("Student Status")] = _("Finish Enrolled")
        elif AttendanceStatusExecutor.attendance_status_is_attended(attr_dict[user_id]):
            record[_("Student Status")] = _("Enrolled")
        else:
            record[_("Student Status")] = _("Not Enrolled")

    else:
        record[_("Student Status")] = _("Not Enrolled")

    return record
