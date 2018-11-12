# -*- coding: utf-8 -*-
import json
import logging

from biz.djangoapps.gx_username_rule.models import OrgUsernameRule
from biz.djangoapps.util.json_utils import EscapedEdxJSONEncoder

from util.json_request import JsonResponse, JsonResponseBadRequest

log = logging.getLogger(__name__)


def get_rules(request):
    rules = OrgUsernameRule.objects.all().values_list('prefix', flat=True)
    return JsonResponse({
        'list': json.dumps([prefix for prefix in rules], cls=EscapedEdxJSONEncoder)
    })
