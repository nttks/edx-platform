"""
Views for login feature
"""
import analytics
from eventtracking import tracker
import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.translation import ugettext as _
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from edxmako.shortcuts import render_to_response
from openedx.core.djangoapps.user_api.accounts import PASSWORD_MIN_LENGTH, PASSWORD_MAX_LENGTH
from openedx.core.djangoapps.user_api.helpers import FormDescription
from student.cookies import set_logged_in_cookies
from student.models import LoginFailures
from student.views import reactivation_email_for_user

from biz.djangoapps.ga_contract.models import ContractAuth
from biz.djangoapps.ga_invitation.models import ContractRegister
from biz.djangoapps.ga_login.models import BizUser, LOGIN_CODE_MIN_LENGTH, LOGIN_CODE_MAX_LENGTH


log = logging.getLogger(__name__)
AUDIT_LOG = logging.getLogger('audit')


@require_GET
@ensure_csrf_cookie
def index(request, url_code):
    # validate url_code of contract
    contract = _validate_and_get_contract(url_code)
    if not contract:
        raise Http404()

    # If we're already logged in
    if request.user.is_authenticated():
        # validate user has bizuser
        if not hasattr(request.user, 'bizuser'):
            raise Http404()

        # validate contract register
        __, contract_register = _validate_and_get_user_contract_register(request.user.bizuser.login_code, contract)
        if not contract_register:
            raise Http404()

        # redirect
        if contract_register.is_input():
            # input -> biz/invitation(302)
            return redirect(reverse('biz:invitation:confirm', kwargs={'invitation_code': contract.invitation_code}))
        else:
            # register -> lms/dashboard(302)
            return redirect(reverse('dashboard'))

    # rendering
    return render_to_response(
        'ga_login/index.html',
        {
            'data': {
                'login_redirect_url': reverse('biz:login:index', kwargs={'url_code': url_code}),
                'platform_name': settings.PLATFORM_NAME,
                'login_form_desc': json.loads(_create_form_descriptions(url_code)),
            },
            'invisible_courseware_navigation': True,
        }
    )


def _validate_and_get_contract(url_code):
    # validate url_code
    try:
        contract = ContractAuth.objects.select_related('contract').get(url_code=url_code).contract
    except ContractAuth.DoesNotExist:
        log.warning(u"Not found contract with url_code:{}".format(url_code))
        return None

    # validate contract
    if not contract.is_enabled():
        log.warning(u"Disabled contract:{} with url_code:{}".format(contract.id, url_code))
        return None

    return contract


def _validate_and_get_user_contract_register(login_code, contract):
    contract_register = ContractRegister.get_by_login_code_contract(login_code, contract)
    if not contract_register:
        log.warning(u"Unknown login_code:{} with contract:{}".format(login_code, contract.id))
        return (None, None)
    if contract_register.is_unregistered():
        log.warning(u"Unregister status user:{} with contract:{}".format(contract_register.user.id, contract.id))
        return (None, None)
    if not contract.enabled_register_by_studentself and not contract_register.is_registered():
        log.warning(u"Student can not be registerd, status is not register:{} user:{} contract:{}".format(contract_register.status, contract_register.user.id, contract.id))
        return (None, None)

    return (contract_register.user, contract_register)


def _create_form_descriptions(url_code):
    """
    Return a description of the login form of json.
    """
    form_desc = FormDescription('post', reverse('biz:login:submit'))

    # for url_code to validate ratelimit on same url.
    form_desc.ALLOWED_TYPES.append('hidden')

    form_desc.add_field(
        'login_code',
        field_type='text',
        label=_(u"Login Code"),
        placeholder=_(u"example: loginCode123"),
        restrictions={
            'min_length': LOGIN_CODE_MIN_LENGTH,
            'max_length': LOGIN_CODE_MAX_LENGTH,
        }
    )

    form_desc.add_field(
        'password',
        label=_(u"Password"),
        field_type='password',
        restrictions={
            'min_length': PASSWORD_MIN_LENGTH,
            'max_length': PASSWORD_MAX_LENGTH,
        }
    )

    form_desc.add_field(
        'url_code',
        field_type='hidden',
        default=url_code,
    )

    form_desc.add_field(
        'remember',
        field_type='checkbox',
        label=_("Remember me"),
        default=False,
        required=False,
    )

    return form_desc.to_json()


@require_POST
@ensure_csrf_cookie
def submit(request):

    # login
    if 'url_code' not in request.POST or 'login_code' not in request.POST or 'password' not in request.POST:
        return HttpResponse(
            _("There was an error receiving your login information. Please email us."),
            status=403
        )

    # validate url_code of contract
    contract = _validate_and_get_contract(request.POST['url_code'])
    if not contract:
        return HttpResponse(
            _("There was an error receiving your login information. Please email us."),
            status=403
        )

    login_code = request.POST['login_code']

    # validate and get user, contract-register
    user_found_by_login_code, __ = _validate_and_get_user_contract_register(login_code, contract)
    if not user_found_by_login_code:
        if settings.FEATURES['SQUELCH_PII_IN_LOGS']:
            log.warning(u"Login failed contract:{0} - Unknown user".format(contract.id))
        else:
            log.warning(u"Login failed contract:{0} - Unknown user {1}".format(contract.id, login_code))

    # see if account has been locked out due to excessive login failures
    if user_found_by_login_code and LoginFailures.is_feature_enabled() and LoginFailures.is_user_locked_out(user_found_by_login_code):
        return HttpResponse(
            _("This account has been temporarily locked due to excessive login failures. Try again later."),
            status=403
        )

    # if the user doesn't exist, we want to set the username to an invalid
    # username so that authentication is guaranteed to fail and we can take
    # advantage of the ratelimited backend
    username = user_found_by_login_code.username if user_found_by_login_code else ''

    password = request.POST['password']
    authenticated_user = authenticate(username=username, password=password)

    if authenticated_user is None:
        # tick the failed login counters if the user exists in the database
        if user_found_by_login_code and LoginFailures.is_feature_enabled():
            LoginFailures.increment_lockout_counter(user_found_by_login_code)

        # if we didn't find this username earlier, the account for this email
        # doesn't exist, and doesn't have a corresponding password
        if username != '':
            if settings.FEATURES['SQUELCH_PII_IN_LOGS']:
                AUDIT_LOG.warning(u"Login failed contract:{0} - password for user.id:{1} is invalid".format(
                    contract.id,
                    user_found_by_login_code.id if user_found_by_login_code else '<unknown>',
                ))
            else:
                AUDIT_LOG.warning(u"Login failed contract:{0} - password for {1} is invalid".format(contract.id, login_code))
        return HttpResponse(_("Login code or password is incorrect."), status=403)

    # successful login, clear failed login attempts counters, if applicable
    if LoginFailures.is_feature_enabled():
        LoginFailures.clear_lockout_counter(authenticated_user)

    # Track the user's sign in
    if hasattr(settings, 'LMS_SEGMENT_KEY') and settings.LMS_SEGMENT_KEY:
        tracking_context = tracker.get_tracker().resolve_context()
        analytics.identify(authenticated_user.id, {
            'email': authenticated_user.email,
            'username': authenticated_user.username
        })

        analytics.track(
            authenticated_user.id,
            'edx.bi.user.account.authenticated_biz',
            {
                'category': 'conversion',
                'label': contract.id,
                'provider': None
            },
            context={
                'ip': tracking_context.get('ip'),
                'Google Analytics': {
                    'clientId': tracking_context.get('client_id')
                }
            }
        )

    if authenticated_user.is_active:
        try:
            # We do not log here, because we have a handler registered
            # to perform logging on successful logins.
            login(request, authenticated_user)
            if request.POST.get('remember') == 'true':
                request.session.set_expiry(getattr(settings, 'SESSION_EXPIRY', 604800))
                log.debug("Setting user session to never expire")
            else:
                request.session.set_expiry(0)
        except Exception as exc:
            AUDIT_LOG.critical("Login failed - Could not create session. Is memcached running?")
            log.critical("Login failed - Could not create session. Is memcached running?")
            log.exception(exc)
            raise

        # Ensure that the external marketing site can
        # detect that the user is logged in.
        return set_logged_in_cookies(request, HttpResponse(status=204), authenticated_user)

    else:

        if settings.FEATURES['SQUELCH_PII_IN_LOGS']:
            AUDIT_LOG.warning(u"Login failed contract:{0} - Account not active for user.id:{1}, resending activation".format(contract.id, authenticated_user.id))
        else:
            AUDIT_LOG.warning(u"Login failed contract:{0} - Account not active for user {1}, resending activation".format(contract.id, login_code))

        reactivation_email_for_user(authenticated_user)

        return HttpResponse(
            _("This account has not been activated. We have sent another activation message. Please check your email for the activation instructions."),
            status=400
        )
