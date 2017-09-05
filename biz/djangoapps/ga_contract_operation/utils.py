from django.conf import settings
from django.core.mail import send_mail as django_send_mail


def replace_braces(target, replace_dict=None):
    """
    Replace the keys enclosed in braces with the values by the dict.

    Args:
        target (str): text (like 'I am {username}.')
        replace_dict (dict): dict for replacement (like {'username': 'staff'})

    Returns: replaced text (like 'I am staff.')
    """
    replace_dict = replace_dict or {}
    for k, v in replace_dict.iteritems():
        target = target.replace('{{{0}}}'.format(k), str(v))
    return target


def send_mail(user, mail_subject, mail_body, replace_dict=None):
    """
    Send replaced mail(subject and body of template).
    """
    mail_subject = replace_braces(mail_subject, replace_dict)
    mail_body = replace_braces(mail_body, replace_dict)
    django_send_mail(mail_subject, mail_body, settings.DEFAULT_FROM_EMAIL, [user.email])
