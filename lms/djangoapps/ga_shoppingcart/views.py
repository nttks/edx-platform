"""
Views for shoppingcart
"""
import logging

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from shoppingcart.processors.exceptions import CCProcessorException

from ga_shoppingcart.notifications import process_notification

NOTIFICATION_RESULT_SUCCESS = '0'

log = logging.getLogger(__name__)


@require_POST
@csrf_exempt
def notify(request):
    try:
        log.info('Begin the process of notification from GMO. params={}'.format(request.POST))
        process_notification(request.POST.copy())
        log.info('Success to process of notification from GMO.')
    except:
        # if Exception occur, record the log for monitoring but no longer need to be notified from GMO.
        # GMO is to retransmit up to a maximum 5 times, every hour if they can not receive a normal status.
        # But we always returns a normal status to them if we recieved a notification even once.
        # In this case, the notification data is an invalid or a DB and inconsistencies.
        # operation suppoer is required.
        log.exception('Failed to process of notification from GMO.')
    return HttpResponse(NOTIFICATION_RESULT_SUCCESS)
