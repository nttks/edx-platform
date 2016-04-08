"""
This module is view of invitation.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET, require_POST

from edxmako.shortcuts import render_to_response

from student.models import CourseEnrollment
from util.json_request import JsonResponse

from lms.djangoapps.courseware.courses import get_course_by_id

from biz.djangoapps.ga_contract.models import Contract
from .models import (
    INPUT_INVITATION_CODE,
    REGISTER_INVITATION_CODE,
    AdditionalInfoSetting,
    ContractRegister,
)


ADDITIONAL_NAME = 'additional_{additional_id}'

log = logging.getLogger(__name__)


@login_required
@require_GET
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
def index(request):
    """
    Display for input invitation code and list of contract register.
    """

    contracts = []
    for contract in [contract_register.contract for contract_register in ContractRegister.find_register_by_user(request.user)]:
        contract.courses = [get_course_by_id(detail.course_id) for detail in contract.details.all()]
        contracts.append(contract)

    return render_to_response('ga_invitation/index.html', {'contracts': contracts})


@login_required
@require_POST
def verify(request):
    """
    Validate invitation code.
    """

    if 'invitation_code' not in request.POST:
        return HttpResponseBadRequest()

    invitation_code = request.POST['invitation_code']
    if not invitation_code:
        return JsonResponse({'result': False, 'message': _('Invitation code is required.')})

    contract = Contract.get_by_invitation_code(invitation_code)
    if not contract or not contract.is_enabled():
        return JsonResponse({'result': False, 'message': _('Invitation code is invalid.')})

    contract_details = contract.details.all()
    if not contract_details:
        log.warning('Not found contract detail, invitation_code(%s), contract_id(%s)', invitation_code, contract.id)
        return JsonResponse({'result': False, 'message': _('Invitation code is invalid.')})

    for detail in contract_details:
        try:
            get_course_by_id(detail.course_id)
        except Http404:
            log.warning('Not found course of contract detail, course_id(%s), contract_detail_id(%s)', detail.course_id, detail.id)
            return JsonResponse({'result': False, 'message': _('Invitation code is invalid.')})

    return JsonResponse({'result': True, 'href': reverse('biz:invitation:confirm', kwargs={'invitation_code': invitation_code})})


@login_required
@require_GET
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@transaction.atomic
def confirm(request, invitation_code):
    """
    Display for confirm course of contract and input additionalinfo of contract.
    """

    contract = Contract.get_by_invitation_code(invitation_code)
    if not contract or not contract.is_enabled():
        log.warning('Contract is None or disabled.')
        raise Http404()

    courses = [get_course_by_id(detail.course_id) for detail in contract.details.all()]
    if not courses:
        log.info('Not found contract detail.')
        raise Http404()

    contract_register, created = ContractRegister.objects.get_or_create(user=request.user, contract=contract)
    if not created and not contract_register.is_registered():
        contract_register.status = INPUT_INVITATION_CODE
        contract_register.save()

    additionals = []
    for additional in contract.additional_info.all():
        additionals.append({
            'name': ADDITIONAL_NAME.format(additional_id=additional.id),
            'display_name': additional.display_name,
            'value': AdditionalInfoSetting.get_value(request.user, contract, additional) if contract_register.is_registered() else ''
        })

    context = {
        'contract': contract,
        'courses': courses,
        'additionals': additionals,
    }

    return render_to_response('ga_invitation/confirm.html', context)


@login_required
@require_POST
def register(request):
    """
    Register invitation code of contract for user.
    """

    if 'invitation_code' not in request.POST:
        return HttpResponseBadRequest()

    invitation_code = request.POST['invitation_code']
    if not invitation_code:
        return JsonResponse({
            'result': False,
            'message': _(
                'Invitation code is invalid. Please operate again from <a href="{index_url}">here</a>.'
            ).format(index_url=reverse('biz:invitation:index'))
        })

    contract = Contract.get_by_invitation_code(invitation_code)
    if not contract or not contract.is_enabled():
        return JsonResponse({
            'result': False,
            'message': _(
                'Invitation code is invalid. Please operate again from <a href="{index_url}">here</a>.'
            ).format(index_url=reverse('biz:invitation:index'))
        })

    contract_details = contract.details.all()
    if not contract_details:
        log.warning('Not found contract detail, invitation_code(%s), contract_id(%s)', invitation_code, contract.id)
        return JsonResponse({
            'result': False,
            'message': _(
                'Invitation code is invalid. Please operate again from <a href="{index_url}">here</a>.'
            ).format(index_url=reverse('biz:invitation:index'))
        })

    for detail in contract_details:
        try:
            get_course_by_id(detail.course_id)
        except Http404:
            log.warning('Not found course of contract detail, course_id(%s), contract_detail_id(%s)', detail.course_id, detail.id)
            return JsonResponse({
                'result': False,
                'message': _(
                    'Invitation code is invalid. Please operate again from <a href="{index_url}">here</a>.'
                ).format(index_url=reverse('biz:invitation:index'))
            })

    contract_additionals = contract.additional_info.all()
    additional_errors = []
    for additional in contract_additionals:
        param_name = ADDITIONAL_NAME.format(additional_id=additional.id)
        if param_name not in request.POST:
            return JsonResponse({
                'result': False,
                'message': _(
                    '{display_name} could not be confirmed. Please operate again from <a href="{confirm_url}">here</a>.'
                ).format(
                    display_name=additional.display_name,
                    confirm_url=reverse('biz:invitation:confirm', kwargs={'invitation_code': invitation_code})
                )
            })

        if not request.POST[param_name]:
            additional_errors.append({
                'name': param_name,
                'message': _('{display_name} is required.').format(display_name=additional.display_name)
            })

    if additional_errors:
        return JsonResponse({'result': False, 'message': '', 'additional_errors': additional_errors})

    try:
        with transaction.atomic():
            # ContractRegister
            contract_register = ContractRegister.get_by_user_contract(request.user, contract)
            contract_register.status = REGISTER_INVITATION_CODE
            contract_register.save()
            # AdditionalInfoSetting
            for additional in contract_additionals:
                AdditionalInfoSetting.set_value(request.user, contract, additional, request.POST[ADDITIONAL_NAME.format(additional_id=additional.id)])
            # CourseEnrollment
            for detail in contract_details:
                CourseEnrollment.enroll(request.user, detail.course_id)
    except Exception:
        log.exception('Can not register invitation code, contract_id(%s), username(%s)', contract.id, request.user.username)
        return JsonResponse({
            'result': False,
            'message': _(
                'Failed to register the invitation code. Please operate again from <a href="{index_url}">here</a>.'
            ).format(index_url=reverse('biz:invitation:index'))
        })

    return JsonResponse({'result': True, 'href': reverse('dashboard')})
