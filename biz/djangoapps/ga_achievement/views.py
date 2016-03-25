"""
outputs the students situation in w2ui screen.
and outputs the students status in the csv file.
"""
import json
import logging
import unicodecsv as csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET

from biz.djangoapps.ga_achievement.models import ScoreBatchStatus
from biz.djangoapps.ga_achievement.score_store import ScoreStore
from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.decorators import check_course_selection
from edxmako.shortcuts import render_to_response
from util.file import course_filename_prefix_generator

log = logging.getLogger(__name__)


@require_GET
@login_required
@check_course_selection
def index(request):
    """
    Display for Students Status Information

    :param request: HttpRequest
    :return: HttpResponse
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    score_batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)
    if score_batch_status:
        score_update_date = datetime_utils.to_jst(score_batch_status.created).strftime('%Y/%m/%d %H:%M')
        score_update_status = _(score_batch_status.status)
    else:
        score_update_date = ''
        score_update_status = ''

    score_store = ScoreStore(contract_id, unicode(course_id))
    columns, records, searches = score_store.get_list()

    context = {
        'columns': json.dumps(columns),
        'records': json.dumps(records),
        'searches': json.dumps(searches),
        'score_update_date': score_update_date,
        'score_update_status': score_update_status,
    }
    return render_to_response('ga_achievement/score.html', context)


@require_GET
@login_required
@check_course_selection
def download_csv(request):
    """
    Data used in the csv file for Students Status Information

    :param request: HttpRequest
    :return: HttpResponse
    """
    contract_id = request.current_contract.id
    course_id = request.current_course.id
    score_batch_status = ScoreBatchStatus.get_last_status(contract_id, course_id)
    if score_batch_status:
        score_update_date = datetime_utils.to_jst(score_batch_status.created).strftime('%Y-%m-%d-%H%M')
    else:
        score_update_date = 'no-timestamp'

    response = HttpResponse(mimetype='text/csv')
    filename = u'{course_prefix}_{csv_name}_{timestamp_str}.csv'.format(
        course_prefix=course_filename_prefix_generator(request.current_course.id),
        csv_name='score_status',
        timestamp_str=score_update_date
    )
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
    # Note: set cookie for jquery.fileDownload
    response['Set-Cookie'] = 'fileDownload=true; path=/'

    student_achievement = ScoreStore(contract_id, unicode(course_id))
    columns, records = student_achievement.get_csv_list()
    writer = csv.writer(response)
    writer.writerow(columns)
    for record in records:
        writer.writerow(record)

    return response
