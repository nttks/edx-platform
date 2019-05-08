# -*- coding: utf-8 -*-
import json
import urllib
import logging
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie

from biz.djangoapps.gx_username_rule.models import OrgUsernameRule
from biz.djangoapps.gx_sso_config.models import SsoConfig
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder

from util.json_request import JsonResponse, JsonResponseBadRequest
from social.apps.django_app.default.models import UserSocialAuth

log = logging.getLogger(__name__)


@ensure_csrf_cookie
def get_org_username_rules(request):
    rules = OrgUsernameRule.objects.all().values_list('prefix', flat=True)
    return JsonResponse({
        'list': json.dumps([prefix for prefix in rules], cls=EscapedEdxJSONEncoder)
    })


@ensure_csrf_cookie
def check_redirect_saml_login(request):
    result = {
        'exist_saml_master': False,
        'redirect_url': '',
    }

    email = request.POST['email'] if 'email' in request.POST else ''
    next_url = request.POST['next'] if 'next' in request.POST else ''

    try:
        login_user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse(result)

    matched_rule = None
    for rule in OrgUsernameRule.objects.all():
        if login_user.username.startswith(rule.prefix):
            matched_rule = rule
            break

    if matched_rule is not None:
        if UserSocialAuth.objects.filter(user=login_user, provider='tpa-saml').count() is not 0:
            idp_slugs = SsoConfig.objects.filter(org=matched_rule.org).values_list('idp_slug', flat=True)
            if len(idp_slugs) is not 0:
                result['exist_saml_master'] = True
                result['redirect_url'] = '/auth/login/tpa-saml/?auth_entry=login&next={next_url}&idp={idp}'.format(
                    next_url=urllib.quote(next_url), idp=idp_slugs[0])

    return JsonResponse(result)
