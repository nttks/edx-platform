# -*- coding: utf-8 -*-
"""
Management command to output biz score playback log from cron.
"""
from courseware.courses import get_course
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import ugettext as _
from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, ScoreBatchStatus
from biz.djangoapps.ga_contract.models import ContractDetail
from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting, ContractRegister
from biz.djangoapps.util import datetime_utils
from xmodule.modulestore.django import modulestore
from boto import connect_s3
from boto.s3.key import Key
from pytz import timezone
import codecs
import copy
import commands
import datetime
import json
import logging
import re
import os
log = logging.getLogger(__name__)
CSV_HEADER = u'"ファイル種別","コースID","スケジュールID","ユーザーメールアドレス","シーケンス（連番）",' \
             u'"受講フラグ","ユーザ名","ジャンル１","ジャンル２","コースID（gacco）","講座名",'

FILE_TYPE = '9'
ms = modulestore()


class Command(BaseCommand):
    help = """
    Usage: python manage.py lms --settings=aws output_achievement -bucket [bucket]
    """
    target_id = None

    def add_arguments(self, parser):
        parser.add_argument('-bucket', required=True)
        parser.add_argument('-mongodb_host', required=True)
        parser.add_argument('-org_id')
        parser.add_argument('-contract_id')
        parser.add_argument('-mode')
        parser.add_argument('-exclude_org_id')
        parser.add_argument('-exclude_contract_id')

    def handle(self, *args, **options):
        target_org_id = options['org_id']
        target_contract_id = options['contract_id']
        exclude_org_id = options['exclude_org_id']
        exclude_contract_id = options['exclude_contract_id']
        target_mode = options['mode']
        s3_bucket_name = options['bucket']
        mongodb_host = options['mongodb_host']

        def _s3bucket_connection():
            try:
                conn = connect_s3()
                # conn = connect_s3(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)
                bucket = conn.get_bucket(s3_bucket_name.split('/')[0])
            except Exception as e:
                log.error(e)
                raise CommandError("Could not establish a connection to S3 for file download. Check your credentials.")
            return bucket

        def _get_user_list_contract(contract_detail, mongo):
            user_dict = {}
            raw_sql = u"""SELECT T1.id, T1.user_id, T1.contract_id, T1.status, T2.email, T2.username, 
                T3.add1, T3.add2, T3.add3
                FROM ga_invitation_contractregister as T1
                LEFT JOIN auth_user as T2
                ON T1.user_id = T2.id
                LEFT JOIN 
                (SELECT user_id, contract_id, MAX(contract_id),
                MAX(CASE display_name WHEN '{0}' THEN value END) as add1,
                MAX(CASE display_name WHEN '{1}' THEN value END) as add2,
                MAX(CASE display_name WHEN '{2}' THEN value END) as add3
                FROM ga_invitation_additionalinfosetting
                WHERE display_name IN ('{0}', '{1}', '{2}')
                GROUP BY user_id, contract_id) as T3
                ON T1.user_id = T3.user_id AND T1.contract_id = T3.contract_id
                WHERE T1.contract_id = %s
            """.format(_('Additional Info') + '1', _('Additional Info') + '2', _('Additional Info') + '3')
            for contract_register in ContractRegister.objects.raw(raw_sql, [str(contract_detail.contract.id)]):
                csv_list = [FILE_TYPE,
                            contract_register.add1 or '',
                            contract_register.add2 or '',
                            contract_register.email,
                            contract_register.add3 or '',
                            'OFF' if contract_register.status == "Unregister" else '',
                            contract_register.username,
                            mongo.category or '',
                            mongo.course_category2 or '',
                            str(contract_detail.course_id),
                            mongo.display_name,
                            ]
                csv_list = ['"'+csv+'"' for csv in csv_list]
                user_dict[contract_register.username] = csv_list
            return user_dict

        def _output_score(user_dict_score, course, update_datetime):
            score_store = ScoreStore(course.contract.id, unicode(course.course_id))

            columns = [col[0] for col in score_store.get_section_names(total_show=True)]
            __, score_data = score_store.get_data_for_w2ui()

            for data in score_data:
                if data[_('Username')] in user_dict_score:
                    for column in columns:
                        if data[column] == score_store.VALUE__NOT_ATTEMPTED:
                            user_dict_score[data[_('Username')]].append('"-"')
                        else:
                            user_dict_score[data[_('Username')]].append('"{:.1f}%"'.format(float(data[column])*100))
            del score_store

            section_dict = {}
            with ms.bulk_operations(course.course_id):
                section_list = ms.get_items(course_key=course.course_id, qualifiers={'category': 'sequential'})
                for section in section_list:
                    for vertical in section.get_children():
                        for module in vertical.get_children():
                            if module.location.category in ['problem']:
                                section_dict[section.display_name] = section.location.block_id

            file_name = str(course.course_id).replace('course-v1:', '') + "_score_data_" + update_datetime + ".csv"

            new_columns = []
            for column in columns:
                for key in section_dict:
                    if column.endswith('___'+key):
                        new_columns.append('"' + section_dict[key] + '_' + column + '__' + _('Score') + '"')
            columns = new_columns

            columns = ['"'+col+'__'+_('Score')+'"' for col in columns]
            strdata = CSV_HEADER + '"' + _('Total Score') + '",' + ','.join(columns) + "\r\n"
            strdata += '\r\n'.join([','.join(x if len(x) != 11 else x + ['"-"'] * len(columns)) for x in
                                    user_dict_score.values()])
            output_csv_s3(file_name, strdata)

        def _output_playback(user_dict_playback, course, update_datetime):
            playback_store = PlaybackStore(course.contract.id, unicode(course.course_id))
            columns = [col[0] for col in playback_store.get_section_names(total_show=True)]
            __, playback_data = playback_store.get_data_for_w2ui()

            for column in columns:
                if re.search(_("Section Playback Time"), column):
                    columns.remove(column)

            for data in playback_data:
                if data[_('Username')] in user_dict_playback:
                    for column in columns:
                        user_dict_playback[data[_('Username')]].append(
                            '"' + str((datetime.timedelta(seconds=data[column]))) + '"')

            vertical_dict = {}
            with ms.bulk_operations(course.course_id):
                vertical_list = ms.get_items(course_key=course.course_id, qualifiers={'category': 'vertical'})
                for vertical in vertical_list:
                    for module in vertical.get_children():
                        if module.location.category in ['video', 'jwplayerxblock']:
                            vertical_dict[vertical.display_name] = vertical.location.block_id

            file_name = str(course.course_id).replace('course-v1:',
                                                      '') + "_dougashichou_data_" + update_datetime + ".csv"

            new_columns = []
            for column in columns:
                for key in vertical_dict:
                    if column.endswith('___'+key):
                        new_columns.append('"' + vertical_dict[key] + '_' + column + '__' + _('Time') + '"')
            columns = new_columns
            # columns = ['"' + col + '__' + _('Time') + '"' for col in columns]

            strdata = CSV_HEADER + u'"合計動画視聴時間",' + ','.join(columns[1:]) + "\r\n"
            strdata += '\r\n'.join([','.join(x if len(x) != 11 else x + ['"0:00:00"'] * len(columns)) for x in
                                    user_dict_playback.values()])
            output_csv_s3(file_name, strdata)

        def _output_playback2(user_dict_playback, course, update_datetime):
            mongodb_query = '{contract_id:' + str(course.contract.id) + ', course_id:"' + unicode(
                course.course_id) + '", document_type:"record"}'
            mongodb_cmd = "mongoexport --db biz --collection playback --out /tmp/output_playback_data.json " \
                          " --username " + settings.BIZ_MONGO['playback']['user'] + \
                          " --password " + settings.BIZ_MONGO['playback']['password'] + \
                          " --host " + mongodb_host + \
                          " --query '" + mongodb_query + "'"
            commands.getoutput(mongodb_cmd)

            json_list = []
            with codecs.open('/tmp/output_playback_data.json', 'r', 'utf8') as fin:
                for line in fin:
                    json_list.append(line)
            if os.path.exists('/tmp/output_playback_data.json'):
                os.remove('/tmp/output_playback_data.json')

            playback_store = PlaybackStore(course.contract.id, unicode(course.course_id))
            columns = [col[0] for col in playback_store.get_section_names(total_show=True)]
            del playback_store

            for column in columns:
                if re.search(_("Section Playback Time"), column):
                    columns.remove(column)

            for data in json_list:
                data = json.loads(data, 'uft-8')
                if data[_('Username')] in user_dict_playback:
                    for column in columns:
                        user_dict_playback[data[_('Username')]].append(
                            '"' + str((datetime.timedelta(seconds=data[column]))) + '"')

            vertical_dict = {}
            with ms.bulk_operations(course.course_id):
                vertical_list = ms.get_items(course_key=course.course_id, qualifiers={'category': 'vertical'})
                for vertical in vertical_list:
                    for module in vertical.get_children():
                        if module.location.category in ['video', 'jwplayerxblock']:
                            vertical_dict[vertical.display_name] = vertical.location.block_id

            file_name = str(course.course_id).replace('course-v1:',
                                                      '') + "_dougashichou_data_" + update_datetime + ".csv"

            new_columns = []
            for column in columns:
                for key in vertical_dict:
                    if column.endswith('___'+key):
                        new_columns.append('"' + vertical_dict[key] + '_' + column + '__' + _('Time') + '"')
            columns = new_columns
            # columns = ['"' + col + '__' + _('Time') + '"' for col in columns]

            strdata = CSV_HEADER + u'"合計動画視聴時間",' + ','.join(columns) + "\r\n"
            strdata += '\r\n'.join([','.join(x if len(x) != 11 else x + ['"0:00:00"'] * len(columns)) for x in
                                    user_dict_playback.values()])
            output_csv_s3(file_name, strdata)

        def output_csv_s3(filename, write):
            with codecs.open("/tmp/" + filename, 'w', 'sjis', 'ignore') as f:
                f.write(write)
            # S3 Connect
            bucket = _s3bucket_connection()
            s3key = Key(bucket)
            s3key.key = '/'.join(s3_bucket_name.split('/')[1:]) + filename
            s3key.set_contents_from_filename("/tmp/" + filename)
            if os.path.exists("/tmp/" + filename):
                os.remove("/tmp/" + filename)

        def output_courses_batch():
            courses = ContractDetail.objects.all()
            if target_org_id:
                courses = courses.filter(contract__contractor_organization_id__in=target_org_id.split(","))
            if exclude_org_id:
                courses = courses.exclude(contract__contractor_organization_id__in=exclude_org_id.split(","))
            if target_contract_id:
                courses = courses.filter(contract_id__in=target_contract_id.split(","))
            if exclude_contract_id:
                courses = courses.exclude(contract_id__in=exclude_contract_id.split(","))

            for course in courses:
                log.info(course.contract.contract_name)

                if course.contract.start_date > datetime.datetime.now(
                        timezone(settings.TIME_ZONE_DISPLAYED_FOR_DEADLINES)).date():
                    continue
                if course.contract.end_date < datetime.datetime.now(
                        timezone(settings.TIME_ZONE_DISPLAYED_FOR_DEADLINES)).date():
                    continue

                try:
                    course_mongo = get_course(course.course_id)
                except Exception as e:
                    log.info(e)
                    continue
                if course_mongo.start > datetime.datetime.now(timezone(settings.TIME_ZONE_DISPLAYED_FOR_DEADLINES)):
                    continue
                if course_mongo.end:
                    course_endline = course_mongo.end + datetime.timedelta(days=3)
                    if course_endline < datetime.datetime.now(timezone(settings.TIME_ZONE_DISPLAYED_FOR_DEADLINES)):
                        continue
                user_dict = _get_user_list_contract(contract_detail=course, mongo=course_mongo)

                if target_mode and target_mode != "score":
                    pass
                else:
                    score_batch_status = ScoreBatchStatus.get_last_status(course.contract, course.course_id)
                    if score_batch_status:
                        update_datetime = datetime_utils.to_jst(score_batch_status.created).strftime('%Y%m%d%H%M')
                        user_dict_score = copy.deepcopy(user_dict)
                        _output_score(user_dict_score, course, update_datetime)
                        del user_dict_score

                if target_mode and target_mode != "playback":
                    pass
                else:
                    playback_batch_status = PlaybackBatchStatus.get_last_status(course.contract, course.course_id)
                    if playback_batch_status:
                        update_datetime = datetime_utils.to_jst(playback_batch_status.created).strftime('%Y%m%d%H%M')
                        user_dict_playback = copy.deepcopy(user_dict)
                        # _output_playback(user_dict_playback, course, update_datetime)
                        _output_playback2(user_dict_playback, course, update_datetime)
                        del user_dict_playback

        translation.activate('ja')
        log.info(u"Command output_achievement started.")
        output_courses_batch()
        log.info(u"Command output_achievement completed.")
        translation.deactivate_all()
        return "output_achievement completed."
