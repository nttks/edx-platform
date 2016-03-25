"""
Views for organization feature
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST

from biz.djangoapps.ga_organization.forms import OrganizationForm
from biz.djangoapps.ga_organization.models import Organization
from biz.djangoapps.util.datetime_utils import format_for_w2ui
from biz.djangoapps.util.decorators import check_course_selection
from edxmako.shortcuts import render_to_response
from openedx.core.lib.json_utils import EscapedEdxJSONEncoder


@require_GET
@login_required
@check_course_selection
def index(request):
    """
    Show organization list view

    :param request: HttpRequest
    :return: HttpResponse
    """
    search_list = Organization.find_by_creator_org(request.current_organization)
    show_list = []
    for i, org in enumerate(search_list):
        show_list.append({
            'recid': i + 1,
            'org_name': org.org_name,
            'org_code': org.org_code,
            'created_by': org.created_by.profile.name,
            'created': format_for_w2ui(org.created),
            'contract_count': org.org_owner_contracts.count(),
            'manager_count': org.managers.count(),
            'detail_url': reverse('biz:organization:detail', kwargs={'selected_id': org.id}),
        })

    context = {
        'org_show_list': json.dumps(show_list, cls=EscapedEdxJSONEncoder),
    }
    return render_to_response('ga_organization/index.html', context)


@require_GET
@login_required
@check_course_selection
def show_register(request):
    """
    Show organization register view

    :param request: HttpRequest
    :return: HttpResponse
    """
    form = OrganizationForm()

    context = {
        'form': form,
    }
    return render_to_response('ga_organization/detail.html', context)


@require_POST
@login_required
@check_course_selection
def register(request):
    """
    Register a new organization and then show list view

    :param request: HttpRequest
    :return: HttpResponse
    """
    form = OrganizationForm(request.POST)

    if form.is_valid():
        # validation successful
        # Add organization info
        org_model = form.save(commit=False)
        org_model.creator_org_id = request.current_organization.id
        org_model.created_by = request.user
        org_model.save()
        messages.info(request, _("The new organization has been added."))
        # return to list view
        return redirect(reverse('biz:organization:index'))
    else:
        # validation failed
        context = {
            'form': form,
        }
        return render_to_response('ga_organization/detail.html', context)


@require_GET
@login_required
@check_course_selection
def detail(request, selected_id):
    """
    Show selected organization detail view

    :param request: HttpRequest
    :param selected_id: selected org id
    :return: HttpResponse
    """
    selected_org = get_object_or_404(Organization, pk=selected_id, creator_org=request.current_manager.org)
    form = OrganizationForm(instance=selected_org)

    context = {
        'form': form,
        'selected_id': selected_id,
    }
    return render_to_response('ga_organization/detail.html', context)


@require_POST
@login_required
@check_course_selection
def edit(request, selected_id):
    """
    Update or delete selected organization and then redirect to list view

    :param request: HttpRequest
    :param selected_id: selected org id
    :return: HttpResponse
    """
    selected_org = get_object_or_404(Organization, pk=selected_id, creator_org=request.current_organization)
    form = OrganizationForm(request.POST, instance=selected_org)

    # for delete
    if request.POST.get('action_name') == 'delete':
        # if the organization have contracts
        if selected_org.org_contractor_contracts.count() > 0:
            messages.error(request, _("The organization cannot be deleted, because it have contracts."))
            context = {
                'form': form,
                'selected_id': selected_id,
            }
            return render_to_response('ga_organization/detail.html', context)
        # delete the org
        selected_org.delete()
        # return to list view
        messages.info(request, _("The organization has been deleted."))
        return redirect(reverse('biz:organization:index'))

    # for update
    if form.is_valid():
        # validation successful
        # Update organization info
        form.save()
        # return to list view
        messages.info(request, _("The organization changes have been saved."))
        return redirect(reverse('biz:organization:index'))
    else:
        # validation failed
        context = {
            'form': form,
            'selected_id': selected_id,
        }
        return render_to_response('ga_organization/detail.html', context)
