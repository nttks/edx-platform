# -*- coding: utf-8 -*-
"""
Views for contract feature
"""
import os
import re
import csv
import codecs
import logging
import  shutil
from boto import connect_s3
from boto.s3.key import Key
from datetime import datetime
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.translation import ugettext_lazy as _

from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.lib.ga_mail_utils import send_mail

from student.models import CourseEnrollment

from biz.djangoapps.ga_contract.models import Contract, ContractDetail, AdditionalInfo
from biz.djangoapps.ga_invitation.models import ContractRegister, REGISTER_INVITATION_CODE, UNREGISTER_INVITATION_CODE, AdditionalInfoSetting
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.gx_register_api.models import APIContractMail, APIGatewayKey
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.gx_username_rule.models import OrgUsernameRule

from biz.djangoapps.gx_member.models import Member
from biz.djangoapps.gx_students_register_batch.models import S3BucketName
from biz.djangoapps.util.unicodetsv_utils import create_csv_response

log = logging.getLogger(__name__)


LOCAL_DIR = '/tmp/'
TARGET_PATH = 'input_data'

def code_dict(user_email='', prefix=''):
    """
    JsonResponse code definition function
    10's ~ 20's : error , response status 400
    30's : success , response status 200
    """
    code = {
    '10':{"code":"10", "message":"parameter error organization"},
    '11':{"code":"11", "message":"parameter error organization. not exists org_id"},
    '12':{"code":"12", "message":"parameter error contract."},
    '13':{"code":"13", "message":"parameter error contract not settings contract details."},
    '14':{"code":"14", "message":"parameter error user_email: not exists member."},
    '15':{"code":"15", "message":"parameter error user_email: {} diffs".format(prefix)},
    '16':{"code":"16", "message":"parameter error user_email: not exists user"},
    '17':{"code":"17", "message":"ERROR: Did not register {}".format(user_email)},
    '18':{"code":"18", "message":"ERROR: Did not unregister {}".format(user_email)},
    '19':{"code":"19", "message":"{} is not taking classes. Or, attendance registration has been canceled".format(user_email)},
    '20':{"code":"20", "message":"Please a method of POST or DELETE"},
    '21':{"code":"21", "message":"not enough url"},
    '22':{"code":"22", "message":"Please a method of POST"},
    '23':{"code":"23", "message":"An unexpected error occurred"},
    '24':{"code":"24", "message":"The number of characters of additional information exceeds 255 characters"},
    '30':{"code":"30", "message":"You got success! student: {} register. And send mail.".format(user_email)},
    '31':{"code":"31", "message":"You got success! student: {} register. And not send mail.".format(user_email)},
    '32':{"code":"32", "message":"Mail information of the current contract is not registered in the database. So, Did not send mail."},
    '33':{"code":"33", "message":"You got success! student: {} unregister.".format(user_email)},
    '34':{"code":"34", "message":"Has completed. It will be reflected in tomorrow."},
    }
    return code

@csrf_exempt
def post_not_enough(request, start):
    """
    This function is API
    Request body include optional setting
    """
    return JsonResponse(code_dict()['21'], status=400)


def _get_api_data(org_id=0, contract_id=0, user_email=''):
    organization = Organization.objects.filter(id=org_id).first()
    contract = Contract.objects.filter(id=contract_id, contractor_organization_id=organization).first()
    user = User.objects.filter(email=user_email).first()
    return organization, contract, user


def _validation_api_data(organization, contract, code, api_key, user=''):
    if not organization:
        log.info(code['10'])
        return code['10']
    if not bool(APIGatewayKey.objects.filter(api_key=api_key, org_id=organization.id)):
        log.info(code['11'])
        return code['11']
    if not contract:
        log.info(code['12'])
        return code['12']
    if contract:
        if not ContractDetail.objects.filter(contract_id=contract.id).first():
            log.info(code['13'])
            return code['13']
    if user:
        if SsoConfig.user_control_process(user.id):
            log.info(code['14'])
            return code['14']
        if not OrgUsernameRule.exists_org_prefix(str=user.username, org=organization.id):
            prefix = OrgUsernameRule.objects.get(org=organization.id).prefix if OrgUsernameRule.objects.filter(org=organization.id).exists() else ''
            log.info(code_dict(prefix=prefix)['15'])
            return code_dict(prefix=prefix)['15']
    return ''


@csrf_exempt
def post_user_name(request, org_id, contract_id, user_email):
    """
    This function is API
    Request body include optional setting
    :param request:
    :param org_id str(int): GET parameter
    :param contract_id str(int): GET parameter
    :param user_email str: GET parameter
    :return: code_dict()
    """

    code = code_dict()
    # check Amazon API Gateway api_key
    if not 'HTTP_X_API_KEY' in request.META:
        return JsonResponse(code['21'], status=400)
    organization, contract, user = _get_api_data(org_id, contract_id, user_email)
    error_code = _validation_api_data(organization, contract, code, request.META['HTTP_X_API_KEY'], user)
    if error_code:
        return JsonResponse(error_code, status=400)
    if not user:
        log.info(code['16'])
        return JsonResponse(code['16'], status=400)
    contract_detail = contract.details.first()
    course = CourseOverview.get_from_id(contract_detail.course_id)
    if request.method == 'POST':
        # This root is status change register.
        try:
            with transaction.atomic():
                register, __ = ContractRegister.objects.get_or_create(user=user, contract=contract)
                register.status = REGISTER_INVITATION_CODE
                register.save()
                CourseEnrollment.enroll(user, contract_detail.course_id)
                _r = re.compile(".*add_.*")
                post_add_keys = list(filter(_r.match, request.POST.keys()))
                add_obj = AdditionalInfo.objects
                if bool(post_add_keys):
                    if len(add_obj.filter(contract_id=contract_id)) < 10:
                        for i in range(len(add_obj.filter(contract_id=contract_id)), 10):
                            additional_info, __ = add_obj.get_or_create(
                                contract=contract,
                                display_name=_("Additional Info") + str(i + 1)
                            )
                            additional_info.save()
                    _counter = 1
                    additional_info_list = add_obj.filter(contract_id=contract_id).order_by('id')
                    _length_post_data = len(post_add_keys)
                    _length_add_list = len(additional_info_list)
                    # Additional info
                    for i in range(0, 11):
                        if _length_add_list == i:
                            break
                        additional_info_setting, created = AdditionalInfoSetting.objects.get_or_create(
                            contract=contract,
                            display_name=additional_info_list[i].display_name,
                            user=user,
                            defaults={'value': request.POST['add_' + str(i + 1)] if 'add_' + str(
                                i + 1) in post_add_keys else ''}
                        )
                        additional_info_setting.save()
                        if not created:
                            if 'add_' + str(i + 1) in post_add_keys:
                                additional_info_setting.value = request.POST[
                                    post_add_keys[post_add_keys.index('add_' + str(i + 1))]]
                                additional_info_setting.save()

                if request.POST.has_key('send_mail_flg') and request.POST['send_mail_flg'] == '1':
                    contract_mail = APIContractMail.get_register_mail(contract)
                    if bool(contract_mail):

                        send_mail(
                            user,
                            contract_mail.mail_subject.encode('utf-8'),
                            contract_mail.mail_body.encode('utf-8'),
                            APIContractMail.register_replace_dict(
                                user=user,
                                fullname=user.profile.name,
                                link_url1=request.POST['link_url1'] if request.POST.has_key('link_url1') else '',
                                link_url2=request.POST['link_url2'] if request.POST.has_key('link_url2') else '',
                                contract_name=contract.contract_name,
                                course_name=course.display_name
                            )
                        )
                        return JsonResponse(code_dict(user_email)['30'])
                    else:
                        return JsonResponse(code['32'])

                else:
                    return JsonResponse(code_dict(user_email)['31'])
        except Exception:
            log.exception('Can not register. contract_id({}), register({})'.format(contract.id,
                                                                                       user_email))
            return JsonResponse(code_dict(user_email)['17'], status=400)

    elif request.method == 'DELETE':
        # This root is status change unregister.
        try:
            with transaction.atomic():
                if bool(ContractRegister.objects.filter(user=user.id, contract=contract.id, status=REGISTER_INVITATION_CODE)):
                    unregister = ContractRegister.objects.get(user=user.id, contract=contract.id, status=REGISTER_INVITATION_CODE)
                    unregister.status = UNREGISTER_INVITATION_CODE
                    unregister.save()
                    CourseEnrollment.unenroll(unregister.user, contract_detail.course_id)
                    return JsonResponse(code_dict(user_email)['33'])
                else:
                    return JsonResponse(code_dict(user_email)['19'], status=400)
        except Exception:
            log.exception('Can not unregister. contract_id({}), unregister({})'.format(contract.id,
                                                                                       user_email))
            return JsonResponse(code_dict(user_email)['18'], status=400)
    else:
        return JsonResponse(code['20'], status=400)


@csrf_exempt
def post_all(request, org_id, contract_id):
    code = code_dict()
    if request.method not in ['POST', 'DELETE']:
        return JsonResponse(code['20'], status=400)
    # check Amazon API Gateway api_key
    if not 'HTTP_X_API_KEY' in request.META:
        return JsonResponse(code['21'], status=400)
    org, contract, __ = _get_api_data(org_id, contract_id)
    error_code = _validation_api_data(org, contract, code, request.META['HTTP_X_API_KEY'])
    if error_code:
        return JsonResponse(error_code, status=400)
    filename = _create_csv_file(request, 'all', org)
    if filename == 'add_error':
        return JsonResponse(code['24'], status=400)
    try:
        _upload_s3_bucket(org_id, contract_id, filename)
        _delete_local_file(filename)
        log.info('Success Upload File All')
        return JsonResponse(code['34'])
    except Exception as e:
        log.info(e)
        _delete_local_file(filename)
        return JsonResponse(code['23'], status=400)


@csrf_exempt
def post_group(request, org_id, contract_id):
    code = code_dict()
    if request.method != 'POST':
        return JsonResponse(code['22'], status=400)
    # check Amazon API Gateway api_key
    if not 'HTTP_X_API_KEY' in request.META:
        return JsonResponse(code['21'], status=400)
    org, contract, __ = _get_api_data(org_id, contract_id)
    error_code = _validation_api_data(org, contract, code, request.META['HTTP_X_API_KEY'])
    if error_code:
        return JsonResponse(error_code, status=400)
    filename = _create_csv_file(request, 'group', org)
    if filename == 'add_error':
        return JsonResponse(code['24'], status=400)
    try:
        _upload_s3_bucket(org_id, contract_id, filename)
        _delete_local_file(filename)
        log.info('Success Upload File Group')
        return JsonResponse(code['34'])
    except Exception as e:
        log.info(e)
        _delete_local_file(filename)
        return JsonResponse(code['23'], status=400)



def _get_post_data(request):
    """
    create columns
    :param request:
    :return: -> list ['value1', ~  '', 'value10', 'link_url1', 'link_url2'], -> str 'add_error' or ''
    """
    add = []
    for i in range(1, 11):
        if 'add_' + str(i) in request.POST:
            if len(request.POST['add_' + str(i)]) > 255:
                return [], 'add_error'
            add += [' '] if request.POST['add_' + str(i)] == '' else [request.POST['add_' + str(i)]]
        else:
            add += ['']
    return [add + [request.POST['link_url' + str(i)] if 'link_url' + str(i) in request.POST else '' for i in range(1, 3)], '']


def _get_emails(request, org, type):
    """
    :param org: -> objects Organization
    :param type: -> str 'all' or 'group'
    :return: -> list emails ['xxx@xxx.xx,', 'yyy@yyy.yy,']
    """
    strip_extra = re.compile(r'[\"\'|\[|\]|\s]')
    email_check = re.compile(r'^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$')
    if type == 'group':
        return [[email] for email in re.split(',', re.sub(strip_extra, '', request.POST['email'])) if bool(re.search(email_check, email))] if 'email' in request.POST else []
    return [[x['user__email']] for x in Member.objects.filter(org=org, is_active=True).values('user__email')]


def _get_date_format():
    """
    :return: -> str '201902080942485'
    """
    return datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]


def _create_header():
    return ['email'] + ['add_' + str(i) for i in range(1, 11)] + ['link_url1', 'link_url2']


def _create_record(request, org, type):
    """
    :param request:
    :param header_length: -> int 1 or
    :param org: -> object Organization
    :param type: -> str 'all' or 'group'
    :return:
    """
    data, message = _get_post_data(request)
    if message:
        return [], message
    return [email + data for email in _get_emails(request, org, type)], ''


def _create_csv_file(request, type, org):
    """
    :param request:
    :param type: -> str 'all' or 'group'
    :param org: -> object Organization
    :return:
    """
    header = _create_header()
    data, message = _create_record(request, org, type)
    if message:
        return message
    send_mail_flg = request.POST['send_mail_flg'] if 'send_mail_flg' in request.POST and request.POST['send_mail_flg'] == '1' else '0'
    filename = 'student_' + type + '_' + request.method + '_' + _get_date_format() + '_' + send_mail_flg + '.csv'
    response = create_csv_response(filename, header, data)
    with codecs.open(LOCAL_DIR + filename, 'w', 'SJIS') as f:
        f.writer.writelines(response.content.decode('SJIS'))
    return filename


def _s3_connect(org_id, contract_id, filename):
    """
    :param org_id: -> int id
    :param contract_id: -> int id
    :param filename: -> str 'aaaaa.csv'
    :return:
    """
    bucket_name = S3BucketName.objects.get(type='student_register_batch').bucket_name
    # conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
    conn = connect_s3()
    bucket = conn.get_bucket(bucket_name)
    key = Key(bucket)
    key.key = org_id + '/' + contract_id + '/' + TARGET_PATH + '/' + filename
    return key


def _upload_s3_bucket(org_id, contract_id, filename):
    """
    :param bucket_info: -> object S3BucketFilePath
    :param filename: -> str 'aaaaa.csv':
    :return:
    """
    upload_key = _s3_connect(org_id, contract_id, filename)
    upload_key.set_contents_from_filename(LOCAL_DIR + filename)
    return '{} file uploading is complete'.format(filename)

def _delete_local_file(filename):
    if os.path.exists('/tmp/' + filename):
        os.remove('/tmp/' + filename)

