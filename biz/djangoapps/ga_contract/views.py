"""
Views for contract feature
"""
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_contract.forms import ContractForm
from biz.djangoapps.ga_contract.models import Contract, ContractDetail, CONTRACT_TYPE, REGISTER_TYPE
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util.datetime_utils import format_for_w2ui
from biz.djangoapps.util.decorators import check_course_selection
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder, LazyEncoder
from edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

log = logging.getLogger(__name__)


class ContractEncoder(LazyEncoder, EscapedEdxJSONEncoder):
    pass


@require_GET
@login_required
@check_course_selection
def index(request):
    """
    Show contract list view

    :param request: HttpRequest
    :return: HttpResponse
    """
    search_contract_list = Contract.find_by_owner(request.current_organization).select_related(
            'contractor_organization', 'owner_organization', 'created_by')

    return render_to_response("ga_contract/index.html", {
        'contract_show_list': json.dumps([{
            'recid': i,
            'contract_name': contract.contract_name,
            'contract_type': dict(CONTRACT_TYPE).get(contract.contract_type, contract.contract_type),
            'register_type': dict(REGISTER_TYPE).get(contract.register_type, contract.register_type),
            'invitation_code': contract.invitation_code,
            'contractor_organization': contract.contractor_organization.org_name,
            'owner_organization': contract.owner_organization.org_name,
            'start_date': format_for_w2ui(contract.start_date),
            'end_date': format_for_w2ui(contract.end_date),
            'created_by': contract.created_by.profile.name,
            'created': format_for_w2ui(contract.created),
            'course_count': contract.details.count(),
            'detail_url': reverse('biz:contract:detail', kwargs={'selected_contract_id': contract.id}),
        } for i, contract in enumerate(search_contract_list, start=1)], cls=ContractEncoder)
    })


@require_GET
@login_required
@check_course_selection
def show_register(request):
    """
    Show contract register view

    :param request: HttpRequest
    :return: HttpResponse
    """
    current_org = request.current_organization

    # check organization has been registered
    if not Organization.find_by_creator_org_without_itself(current_org):
        messages.error(request, _("You need to create an organization first."))
        return redirect(reverse('biz:contract:index'))

    return render_to_response("ga_contract/detail.html", {
        'form': ContractForm(current_org),
        'detail_list': [],
        'course_list': _get_course_name_list(current_org.org_code),
    })


@require_POST
@login_required
@check_course_selection
def register(request):
    """
    Register a new contract and then show list view

    :param request: HttpRequest
    :return: HttpResponse
    """
    current_org = request.current_organization
    form = ContractForm(current_org, request.POST)

    # contract detail list
    detail_list = _get_detail_input_list(request)
    if detail_list is None:
        # validation failed
        messages.error(request, _("Invalid contract details."))
        return render_to_response("ga_contract/detail.html", {
            'form': form,
            'detail_list': [],
            'course_list': _get_course_name_list(current_org.org_code),
        })

    if form.is_valid():
        # validation successful
        # add new contract info
        contract = form.save(commit=False)
        contract.created_by = request.user
        contract.contractor_organization = form.cleaned_data['contractor_organization']
        contract.owner_organization = current_org
        contract.save()

        # add new contract detail info
        for detail_info in detail_list:
            contract_detail = ContractDetail(contract=contract, course_id=detail_info['course_id'])
            contract_detail.save()

        # return to list view
        messages.info(request, _('The new contract has been added.'))
        return redirect(reverse('biz:contract:index'))
    else:
        # validation failed
        return render_to_response("ga_contract/detail.html", {
            'form': form,
            'detail_list': json.dumps(detail_list),
            'course_list': _get_course_name_list(current_org.org_code),
        })


@require_GET
@login_required
@check_course_selection
def detail(request, selected_contract_id):
    """
    Show selected contract detail view

    :param request: HttpRequest
    :param selected_contract_id: selected contract id
    :return: HttpResponse
    """
    current_org = request.current_organization
    selected_contract = get_object_or_404(Contract, pk=selected_contract_id, owner_organization=current_org)

    return render_to_response("ga_contract/detail.html", {
        'selected_contract_id': selected_contract_id,
        'form': ContractForm(current_org, instance=selected_contract),
        'detail_list': json.dumps([{
            'id': contract_detail.id,
            'course_id': unicode(contract_detail.course_id),
            'delete_flg': '',
        } for contract_detail in selected_contract.details.all()]),
        'course_list': _get_course_name_list(current_org.org_code),
    })


@require_POST
@login_required
@check_course_selection
def edit(request, selected_contract_id):
    """
    Update or delete selected contract and then redirect to list view

    :param request: HttpRequest
    :param selected_contract_id: selected contract id
    :return: HttpResponse
    """
    current_org = request.current_organization
    selected_contract = get_object_or_404(Contract, pk=selected_contract_id, owner_organization=current_org)
    form = ContractForm(request.current_organization, request.POST, instance=selected_contract)

    # contract detail list
    detail_list = _get_detail_input_list(request)
    if detail_list is None:
        # validation failed
        messages.error(request, _("Invalid contract details."))
        return render_to_response("ga_contract/detail.html", {
            'selected_contract_id': selected_contract_id,
            'form': form,
            'detail_list': json.dumps([{
                'id': contract_detail.id,
                'course_id': unicode(contract_detail.course_id),
                'delete_flg': '',
            } for contract_detail in selected_contract.details.all()]),
            'course_list': _get_course_name_list(current_org.org_code),
        })

    context = {
        'selected_contract_id': selected_contract_id,
        'form': form,
        'detail_list': json.dumps(detail_list),
        'course_list': _get_course_name_list(request.current_organization.org_code),
        'url': reverse('biz:contract:edit', kwargs={'selected_contract_id': selected_contract_id}),
    }

    # do delete
    if request.POST.get('action_name') == 'delete':
        if selected_contract.contract_register.count() > 0:
            # # if the invitation code has been registered
            messages.error(request, _("The contract cannot be deleted, because invitation code has been registered."))
            return render_to_response("ga_contract/detail.html", context)
        else:
            # delete the contract
            selected_contract.delete()
            messages.info(request, _("The contract has been deleted."))
            return redirect(reverse('biz:contract:index'))

    # do update
    if form.is_valid():
        # validation successful
        # check invitation code has changed
        if 'invitation_code' in form.changed_data and selected_contract.contract_register.count() > 0:
            messages.error(request, _("The invitation code cannot be changed, because invitation code has been registered."))
            return render_to_response("ga_contract/detail.html", context)

        # Update contract info
        form.save()
        # Update contract detail info
        for detail_info in detail_list:
            contract_detail = ContractDetail(contract=selected_contract, course_id=detail_info['course_id'])
            if detail_info['id']:
                contract_detail.id = detail_info['id']
            if detail_info['delete_flg']:
                contract_detail.delete()
            else:
                contract_detail.save()

        # return to list view
        messages.info(request, _("The contract changes have been saved."))
        return redirect(reverse('biz:contract:index'))
    else:
        # validation failed
        return render_to_response("ga_contract/detail.html", context)


def _get_detail_input_list(request):
    """
    return the list of courses input

    :param request: HttpRequest
    :return: course list
    """
    if not (len(request.POST.getlist('detail_id')) == len(request.POST.getlist('detail_course')) == len(request.POST.getlist('detail_delete'))):
        log.warning('Invalid contract details. detail_id:{}, detail_course:{}, detail_delete:{}.'.format(
            request.POST.getlist('detail_id'),
            request.POST.getlist('detail_course'),
            request.POST.getlist('detail_delete'),
        ))
        return None

    return [{
        'id': detail_id,
        'course_id': course_id,
        'delete_flg': detail_delete,
    } for detail_id, course_id, detail_delete in zip(
        request.POST.getlist('detail_id'),
        request.POST.getlist('detail_course'),
        request.POST.getlist('detail_delete')
    )]


def _get_course_name_list(org_code):
    """
    return \list of organization courses

    :param org_code: organization code
    :return: course list
    """
    return [
        (unicode(c.id), u'{} ({})'.format(c.display_name, c.id))
        for c in CourseOverview.objects.filter(org=org_code).order_by('id')
    ]
