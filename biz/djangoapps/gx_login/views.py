"""
Views for contract feature
"""
import logging
from edxmako.shortcuts import render_to_response
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect
from django.core.urlresolvers import reverse
from biz.djangoapps.ga_manager.models import Manager

log = logging.getLogger(__name__)

LOGIN_ADMIN = 1
LOGIN_ERROR = -1
LOGIN_DEFAULT = 0
LOGIN_ERROR_AUTH = -2


def index(request):
    """
    lists content of Login
    """
    next_url = request.GET.get('next', '')

    if request.user.is_active:
        if request.user.is_authenticated():
            if next_url == '':
                return redirect(reverse('biz:index'))
            else:
                return redirect(next_url)

    account_check = LOGIN_DEFAULT
    post_email = request.POST.get('email', '')
    post_password = request.POST.get("password")
    post_remember = False
    if request.method == 'POST':
        next_url = request.POST.get("next", '')
        if "remember" in request.POST:
            post_remember = True
        if not 0 < len(post_email) <= 255:
            log.info('Login failed - email length over')
            account_check = LOGIN_ERROR
        if not 0 < len(post_password) <= 255:
            log.info('Login failed - password length over')
            account_check = LOGIN_ERROR

        if User.objects.filter(email=post_email, is_active=True).exists():
            user = User.objects.get(email=post_email, is_active=True)
        else:
            log.info("Login failed - password for {0} is invalid".format(post_email))
            account_check = LOGIN_ERROR

        if account_check == LOGIN_ERROR:
            return render_to_response('gx_login/login.html', {'account_check': account_check, 'next_url': next_url, 'email': post_email})

        if user.check_password(post_password):
            mgs = Manager.get_managers(user)
            if any([mg.is_aggregator() for mg in mgs]):
                account_check = LOGIN_ADMIN
            if any([mg.is_director() for mg in mgs]):
                account_check = LOGIN_ADMIN
            if any([mg.is_manager() for mg in mgs]):
                account_check = LOGIN_ADMIN
            if any([mg.is_platformer() for mg in mgs]):
                account_check = LOGIN_ADMIN
            if account_check == LOGIN_ADMIN:
                # Auto Updating Last Login Datetime
                user = authenticate(username=user.username, password=post_password)
                login(request, user)
                if post_remember:
                    # Session Retention 7 days
                    request.session.set_expiry(604800)
                else:
                    request.session.set_expiry(0)
                if next_url == '':
                    return redirect(reverse('biz:index'))
                else:
                    return redirect(next_url)
            else:
                account_check = LOGIN_ERROR_AUTH
        else:
            log.info('Login failed - password mismatch')
            account_check = LOGIN_ERROR
    return render_to_response('gx_login/login.html', {'account_check': account_check, 'next_url': next_url, 'email': post_email})

