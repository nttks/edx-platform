"""
Views for achievement feature
"""
import json
import logging
import unicodecsv as csv

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_achievement.models import PlaybackBatchStatus, ScoreBatchStatus
from biz.djangoapps.ga_achievement.achievement_store import PlaybackStore, ScoreStore
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.decorators import check_course_selection
from edxmako.shortcuts import render_to_response
from util.file import course_filename_prefix_generator
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
def score(request):
    """
    Returns response for score status

    :param request: HttpRequest
    :return: HttpResponse
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    score_batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)
    if score_batch_status:
        update_datetime = datetime_utils.to_jst(score_batch_status.created).strftime('%Y/%m/%d %H:%M')
        update_status = _(score_batch_status.status)
    else:
        update_datetime = ''
        update_status = ''

    score_store = ScoreStore(contract_id, unicode(course_id))
    score_columns, score_records = score_store.get_data_for_w2ui(limit=settings.BIZ_MONGO_LIMIT_RECORDS)
    total_records = score_store.get_record_count()

    context = {
        'update_datetime': update_datetime,
        'update_status': update_status,
        'score_columns': json.dumps(score_columns),
        'score_records': json.dumps(score_records),
        'total_records': total_records,
    }
    return render_to_response('ga_achievement/score.html', context)


@require_POST
@login_required
@check_course_selection
def score_ajax(request):
    """
    Returns response for score status when ajax request

    :param request: HttpRequest
    :return: JsonResponse object with success/error message.
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    try:
        record_offset = int(request.POST['offset'])
        score_store = ScoreStore(contract_id, unicode(course_id))
        __, score_records = score_store.get_data_for_w2ui(offset=record_offset, limit=settings.BIZ_MONGO_LIMIT_RECORDS)
        total_records = score_store.get_record_count()
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponseBadRequest(_("An error has occurred while loading. Please wait a moment and try again."))

    content = {
        'status': 'success',
        'score_records': score_records,
        'total_records': total_records,
    }
    return JsonResponse(content)


@require_POST
@login_required
@check_course_selection
def score_download_csv(request):
    """
    Returns response for download of score status csv

    :param request: HttpRequest
    :return: HttpResponse
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)
    if batch_status:
        update_datetime = datetime_utils.to_jst(batch_status.created).strftime('%Y-%m-%d-%H%M')
    else:
        update_datetime = 'no-timestamp'

    response = HttpResponse(content_type='application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
        course_prefix=course_filename_prefix_generator(request.current_course.id),
        csv_name='score_status',
        timestamp_str=update_datetime,
    )
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    # Note: set cookie for jquery.fileDownload
    response['Set-Cookie'] = 'fileDownload=true; path=/'

    score_store = ScoreStore(contract_id, unicode(course_id))
    columns, records = score_store.get_data_for_csv()
    if columns and records:
        writer = csv.writer(response)
        writer.writerow(columns)
        for record in records:
            writer.writerow(record)

    return response


@require_GET
@login_required
@check_course_selection
def playback(request):
    """
    Returns response for playback status

    :param request: HttpRequest
    :return: HttpResponse
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    batch_status = PlaybackBatchStatus.get_last_status(contract_id, course_id)
    if batch_status:
        update_datetime = datetime_utils.to_jst(batch_status.created).strftime('%Y/%m/%d %H:%M')
        update_status = _(batch_status.status)
    else:
        update_datetime = ''
        update_status = ''

    playback_store = PlaybackStore(contract_id, unicode(course_id))
    playback_columns, playback_records = playback_store.get_data_for_w2ui(limit=settings.BIZ_MONGO_LIMIT_RECORDS)
    total_records = playback_store.get_record_count()

    context = {
        'update_datetime': update_datetime,
        'update_status': update_status,
        'playback_columns': json.dumps(playback_columns),
        'playback_records': json.dumps(playback_records),
        'total_records': total_records,
    }
    return render_to_response('ga_achievement/playback.html', context)


@require_POST
@login_required
@check_course_selection
def playback_ajax(request):
    """
    Returns response for playback status when ajax request

    :param request: HttpRequest
    :return: JsonResponse object with success/error message.
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    try:
        record_offset = int(request.POST['offset'])
        playback_store = PlaybackStore(contract_id, unicode(course_id))
        __, playback_records = playback_store.get_data_for_w2ui(offset=record_offset,
                                                                limit=settings.BIZ_MONGO_LIMIT_RECORDS)
        total_records = playback_store.get_record_count()
    except Exception as e:
        log.exception('Caught the exception: ' + type(e).__name__)
        return JsonResponseBadRequest(_("An error has occurred while loading. Please wait a moment and try again."))

    content = {
        'status': 'success',
        'playback_records': playback_records,
        'total_records': total_records,
    }
    return JsonResponse(content)


@require_POST
@login_required
@check_course_selection
def playback_download_csv(request):
    """
    Returns response for download of playback status csv

    :param request: HttpRequest
    :return: HttpResponse
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    batch_status = PlaybackBatchStatus.get_last_status(contract_id, course_id)
    if batch_status:
        update_datetime = datetime_utils.to_jst(batch_status.created).strftime('%Y-%m-%d-%H%M')
    else:
        update_datetime = 'no-timestamp'

    response = HttpResponse(content_type='application/octet-stream')
    response['X-Content-Type-Options'] = 'nosniff'
    filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
        course_prefix=course_filename_prefix_generator(request.current_course.id),
        csv_name='playback_status',
        timestamp_str=update_datetime,
    )
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    # Note: set cookie for jquery.fileDownload
    response['Set-Cookie'] = 'fileDownload=true; path=/'

    playback_store = PlaybackStore(contract_id, unicode(course_id))
    columns, records = playback_store.get_data_for_csv()
    if columns and records:
        writer = csv.writer(response)
        writer.writerow(columns)
        for record in records:
            writer.writerow(record)

    return response
