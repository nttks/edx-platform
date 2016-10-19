from django.contrib.auth.models import User
from django.db import models

LOGIN_CODE_MIN_LENGTH = 2
LOGIN_CODE_MAX_LENGTH = 30


class BizUser(models.Model):
    """
    This table contains user info to login.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
    )
    login_code = models.CharField(max_length=LOGIN_CODE_MAX_LENGTH)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'ga_login'
