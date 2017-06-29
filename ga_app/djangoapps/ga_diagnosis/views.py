import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET, require_POST
from django.views.generic.edit import FormView

from .models import DiagnosisInfo, GeneratePDFState
from .radar_chart import get_radar_chart_with_base64
from .tasks import perform_create_pdf
from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.ga_invitation.models import ContractRegister, REGISTER_INVITATION_CODE
from course_modes.models import CourseMode
from edxmako.shortcuts import render_to_response
from forms import (DiagnosisBlockA1Form, DiagnosisBlockA2Form, DiagnosisBlockA3Form,
                   DiagnosisBlockB1Form, DiagnosisBlockB2Form, RegulationChoiceForm)
from opaque_keys.edx.keys import CourseKey
from student.models import CourseEnrollment
from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


def check_diagnosis_info(view_func):
    """
    User who not have DiagnosisInfo, redirect to not found page.
    """

    def _wrapped_view_func(request, *args, **kwargs):
        course_id = CourseKey.from_string(kwargs['course_id'])
        try:
            info = DiagnosisInfo.objects.get(
                user=request.user,
                course_id=course_id,
            )
        except DiagnosisInfo.DoesNotExist:
            raise Http404

        kwargs['diagnosis_info'] = info
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


def check_diagnosis_finished(view_func):
    """
    User who completed diagnosis, redirect to result view.
    """
    def _wrapped_view_func(request, *args, **kwargs):
        result_kwargs = {'course_id': kwargs['course_id']}
        result_path = reverse('ga_app:diagnosis:result', kwargs=result_kwargs)
        if request.path != result_path:
            diagnosis_info = kwargs.get('diagnosis_info')
            if not diagnosis_info:
                raise ValueError('DiagnosisInfo was not set.')
            elif diagnosis_info.finished:
                return redirect(result_path)
        return view_func(request, *args, **kwargs)
    return _wrapped_view_func


def check_referer(view_func):
    """ Prevent invasion from direct access or access from incorrect route. """

    url_list1 = [
        'ga_app:diagnosis:block_a1',
        'ga_app:diagnosis:block_a2',
        'ga_app:diagnosis:pre_result_a',
        'ga_app:diagnosis:block_a3',
        'ga_app:diagnosis:block_b1',
        'ga_app:diagnosis:pre_result_b',
        'ga_app:diagnosis:block_b2',
    ]
    url_list2 = [
        'ga_app:diagnosis:index',
        'ga_app:diagnosis:block_a1',
        'ga_app:diagnosis:block_a2',
        'ga_app:diagnosis:pre_result_a',
        'ga_app:diagnosis:index',
        'ga_app:diagnosis:block_b1',
        'ga_app:diagnosis:pre_result_b',
    ]

    def _wrapped_view_func(request, *args, **kwargs):
        def _require_redirect(_url1, _url2):
            if reverse(_url1, kwargs=kwargs) == request.path:
                return reverse(_url2, kwargs=kwargs) not in referer
            return False

        course_id = kwargs['course_id']
        referer = request.META.get('HTTP_REFERER')
        index_path = reverse('ga_app:diagnosis:index', kwargs={'course_id': course_id})
        if not referer and index_path != request.path:
            return redirect(index_path)
        if request.path not in referer:
            for url1, url2 in zip(url_list1, url_list2):
                if _require_redirect(url1, url2):
                    return redirect(reverse('ga_app:diagnosis:index', kwargs={'course_id': course_id}))
        return view_func(request, *args, **kwargs)

    return _wrapped_view_func


class DiagnosisBaseView(FormView):
    timestamp_id = None

    def get_context_data(self, **kwargs):
        context = super(DiagnosisBaseView, self).get_context_data(**kwargs)
        course_id = kwargs['course_id']
        context.update({'course_id': course_id})
        diagnosis_info = kwargs['diagnosis_info']
        context.update(
            {'is_gacco_regulation_state': diagnosis_info.regulation_state == int(DiagnosisInfo.REGULATION_B)}
        )
        return context


class IndexView(DiagnosisBaseView):
    template_name = 'ga_diagnosis/index.html'
    form_class = RegulationChoiceForm

    def __init__(self, **kwargs):
        self.timestamp_id = DiagnosisInfo.TIMESTAMP1
        super(IndexView, self).__init__(**kwargs)

    @method_decorator(login_required)
    def get(self, request, *args, **kwargs):
        course_id = CourseKey.from_string(kwargs['course_id'])
        if str(course_id) not in settings.GA_DIAGNOSIS_ALLOW_COURSE_ID_LIST:
            raise Http404
        diagnosis_info, _ = DiagnosisInfo.objects.get_or_create(
            user=request.user,
            course_id=course_id,
        )
        if diagnosis_info.finished:
            return redirect(
                reverse('ga_app:diagnosis:result', kwargs={'course_id': str(course_id)})
            )
        return render_to_response(self.template_name, settings.GA_DIAGNOSIS_REGULATION)

    @method_decorator(login_required)
    @method_decorator(check_diagnosis_info)
    def post(self, request, *args, **kwargs):
        course_id = kwargs['course_id']
        diagnosis_info = kwargs['diagnosis_info']
        diagnosis_info.set_timestamp(self.timestamp_id)
        f = self.form_class(data=request.POST, instance=diagnosis_info)
        if f.is_valid():
            if f.cleaned_data['regulation_state'] == DiagnosisInfo.REGULATION_A:
                url = reverse('ga_app:diagnosis:block_a1', kwargs={'course_id': course_id})
            elif f.cleaned_data['regulation_state'] == DiagnosisInfo.REGULATION_B:
                url = reverse('ga_app:diagnosis:block_b1', kwargs={'course_id': course_id})
            else:
                return Http404
            f.save()
            return redirect(url)
        context = {'form': f}
        context.update(settings.GA_DIAGNOSIS_REGULATION)
        return render_to_response(self.template_name, context)


class BlockA1(DiagnosisBaseView):
    template_name = 'ga_diagnosis/block_a1.html'
    form_class = DiagnosisBlockA1Form

    def __init__(self, **kwargs):
        self.timestamp_id = DiagnosisInfo.TIMESTAMP2_1
        super(BlockA1, self).__init__(**kwargs)

    @method_decorator(login_required)
    @method_decorator(check_referer)
    @method_decorator(check_diagnosis_info)
    @method_decorator(check_diagnosis_finished)
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context.update({'form': self.form_class()})
        return render_to_response(self.template_name, context)

    @method_decorator(login_required)
    @method_decorator(check_diagnosis_info)
    def post(self, request, *args, **kwargs):
        course_id = kwargs['course_id']
        diagnosis_info = kwargs['diagnosis_info']
        diagnosis_info.set_timestamp(self.timestamp_id)
        f = self.form_class(data=request.POST, instance=diagnosis_info)
        if f.is_valid():
            f.save()
            url = reverse('ga_app:diagnosis:block_a2', kwargs={'course_id': course_id})
            return redirect(url)
        context = self.get_context_data(**kwargs)
        context.update({'form': f})
        return render_to_response(self.template_name, context)


class BlockA2B1Base(DiagnosisBaseView):
    template_name = 'ga_diagnosis/block_a2_or_b1.html'
    url = None

    @method_decorator(login_required)
    @method_decorator(check_referer)
    @method_decorator(check_diagnosis_info)
    @method_decorator(check_diagnosis_finished)
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context.update({'form': self.form_class()})
        return render_to_response(self.template_name, context)

    @method_decorator(login_required)
    @method_decorator(check_diagnosis_info)
    def post(self, request, *args, **kwargs):
        diagnosis_info = kwargs['diagnosis_info']
        diagnosis_info.set_timestamp(self.timestamp_id)
        f = self.form_class(data=request.POST, instance=diagnosis_info)
        if f.is_valid():
            f.save()
            return redirect(self.url)
        context = self.get_context_data(**kwargs)
        context.update({'form': f})
        return render_to_response(self.template_name, context)


class BlockA2(BlockA2B1Base):
    form_class = DiagnosisBlockA2Form

    def __init__(self, **kwargs):
        self.timestamp_id = DiagnosisInfo.TIMESTAMP2_2
        super(BlockA2, self).__init__(**kwargs)

    def post(self, request, *args, **kwargs):
        course_id = kwargs['course_id']
        self.url = reverse('ga_app:diagnosis:pre_result_a', kwargs={'course_id': course_id})
        return super(BlockA2, self).post(request, *args, **kwargs)


class BlockB1(BlockA2B1Base):
    form_class = DiagnosisBlockB1Form

    def __init__(self, **kwargs):
        self.timestamp_id = DiagnosisInfo.TIMESTAMP2_1
        super(BlockB1, self).__init__(**kwargs)

    def post(self, request, *args, **kwargs):
        course_id = kwargs['course_id']
        self.url = reverse('ga_app:diagnosis:pre_result_b', kwargs={'course_id': course_id})
        return super(BlockB1, self).post(request, *args, **kwargs)


class PreResult(DiagnosisBaseView):
    template_name = 'ga_diagnosis/pre_result.html'

    def __init__(self, **kwargs):
        self.timestamp_id = DiagnosisInfo.TIMESTAMP3
        super(PreResult, self).__init__(**kwargs)

    @method_decorator(login_required)
    @method_decorator(check_referer)
    @method_decorator(check_diagnosis_info)
    @method_decorator(check_diagnosis_finished)
    def get(self, request, *args, **kwargs):
        diagnosis_info = kwargs['diagnosis_info']
        radar_chart = get_radar_chart_with_base64(diagnosis_info.get_chart_data(is_pre_result=True))
        context = self.get_context_data(**kwargs)
        context.update({'radar_chart': radar_chart})
        return render_to_response(self.template_name, context)

    @method_decorator(login_required)
    @method_decorator(check_diagnosis_info)
    def post(self, request, *args, **kwargs):
        course_id = kwargs['course_id']
        diagnosis_info = kwargs['diagnosis_info']
        diagnosis_info.set_timestamp(self.timestamp_id)
        context = {
            'course_id': course_id,
        }
        if diagnosis_info.regulation_state == int(DiagnosisInfo.REGULATION_A):
            url = reverse('ga_app:diagnosis:block_a3', kwargs=context)
        elif diagnosis_info.regulation_state == int(DiagnosisInfo.REGULATION_B):
            url = reverse('ga_app:diagnosis:block_b2', kwargs=context)
        else:
            raise Http404
        diagnosis_info.save()
        return redirect(url)


class DiagnosisA3B2BaseView(DiagnosisBaseView):
    def __init__(self, **kwargs):
        self.timestamp_id = DiagnosisInfo.TIMESTAMP4
        super(DiagnosisA3B2BaseView, self).__init__(**kwargs)

    @method_decorator(login_required)
    @method_decorator(check_referer)
    @method_decorator(check_diagnosis_info)
    @method_decorator(check_diagnosis_finished)
    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context.update({'form': self.form_class()})
        return render_to_response(self.template_name, context)

    @method_decorator(transaction.non_atomic_requests)
    def dispatch(self, *args, **kwargs):  # pylint: disable=missing-docstring
        return super(DiagnosisA3B2BaseView, self).dispatch(*args, **kwargs)

    @method_decorator(login_required)
    @method_decorator(check_diagnosis_info)
    def post(self, request, *args, **kwargs):
        course_id = CourseKey.from_string(kwargs['course_id'])
        diagnosis_info = kwargs['diagnosis_info']
        diagnosis_info.set_timestamp(self.timestamp_id)
        diagnosis_info.set_finished()
        f = self.form_class(data=request.POST.copy(), instance=diagnosis_info)
        if f.is_valid():
            with transaction.atomic():
                # Save DiagnosisInfo
                f.save()

                # Create GeneratePDFState if not created.
                pdf_state, __ = GeneratePDFState.objects.get_or_create(diagnosis_info=diagnosis_info)

                # Enroll specific courses automatically.
                self._auto_enroll(diagnosis_info)

            # Notify Celery task operation.
            pdf_state.async_generate_pdf()

            url = reverse('ga_app:diagnosis:result', kwargs={'course_id': str(course_id)})
            return redirect(url)
        context = self.get_context_data(**kwargs)
        context.update({'form': f})

        return render_to_response(self.template_name, context)

    @staticmethod
    def _auto_enroll(diagnosis_info):
        for auto_enrollment_course_id in settings.GA_DIAGNOSIS_AUTO_ENROLLMENT_COURSES:
            course_key = CourseKey.from_string(auto_enrollment_course_id)
            available_modes = CourseMode.modes_for_course_dict(course_key)
            enroll_mode = CourseMode.auto_enroll_mode(course_key, available_modes)
            CourseEnrollment.enroll(
                diagnosis_info.user,
                course_key,
                check_access=True,
                mode=enroll_mode
            )
        register, __ = ContractRegister.objects.get_or_create(
            user=diagnosis_info.user,
            contract=Contract.objects.get(id=settings.GA_DIAGNOSIS_CONTRACT_ID)
        )
        register.status = REGISTER_INVITATION_CODE
        register.save()


class BlockA3(DiagnosisA3B2BaseView):
    template_name = 'ga_diagnosis/block_a3.html'
    form_class = DiagnosisBlockA3Form


class BlockB2(DiagnosisA3B2BaseView):
    template_name = 'ga_diagnosis/block_b2.html'
    form_class = DiagnosisBlockB2Form


@login_required
@require_GET
@check_diagnosis_info
def result(request, course_id, diagnosis_info):
    if not diagnosis_info.finished:
        url = reverse('ga_app:diagnosis:index', kwargs={'course_id': course_id})
        return render_to_response(url)
    try:
        generate_pdf_state = GeneratePDFState.objects.get(diagnosis_info=diagnosis_info)
    except GeneratePDFState.DoesNotExist:
        raise Http404

    radar_chart = get_radar_chart_with_base64(diagnosis_info.get_chart_data(is_pre_result=False))
    context = {
        'course_id': course_id,
        'radar_chart': radar_chart,
        'generate_pdf_state': generate_pdf_state,
    }
    return render_to_response('ga_diagnosis/result.html', context)


@login_required
@require_POST
def get_pdf_status(request, course_id):
    try:
        diagnosis_info, _ = DiagnosisInfo.objects.get_or_create(
            user=request.user,
            course_id=CourseKey.from_string(course_id),
        )
        state = GeneratePDFState.objects.get(diagnosis_info=diagnosis_info)
    except Exception as e:
        log.exception('Caught some exception: {}'.format(e))
        return JsonResponse({
            'state': GeneratePDFState.error,
        })
    return JsonResponse({
        'state': state.status,
        'download_url': state.download_url,
    })
