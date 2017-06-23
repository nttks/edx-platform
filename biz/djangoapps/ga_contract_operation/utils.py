from django.conf import settings
from django.core.mail import send_mail as django_send_mail


def send_mail(user, mail_subject, mail_body, replace_dict=None):
    """
    Send replaced mail(subject and body of template).
    """
    replace_dict = replace_dict or {}
    def _replace(target):
        for key, value in replace_dict.iteritems():
            target = target.replace('{{{0}}}'.format(key), value)
        return target

    django_send_mail(_replace(mail_subject), _replace(mail_body), settings.DEFAULT_FROM_EMAIL, [user.email])
