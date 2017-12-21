"""
Mask methods for working with user objects.
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.utils.crypto import get_random_string
from social.apps.django_app import utils as social_utils

from biz.djangoapps.ga_invitation.models import AdditionalInfoSetting
from bulk_email.models import Optout
from certificates.models import CertificateStatuses, GeneratedCertificate
from student.models import CourseEnrollmentAllowed, ManualEnrollmentAudit, PendingEmailChange
from third_party_auth import pipeline
from openedx.core.djangoapps.course_global.models import CourseGlobalSetting
from pdfgen.certificate import CertificatePDF

from ga_shoppingcart.models import PersonalInfo

log = logging.getLogger(__name__)


def disable_user_info(user):
    """
    Override masked value to user information.

    Note: We can `NEVER` restore the masked value.
    """
    # To force opt-out state since global course is to be registered on a daily batch.
    global_course_ids = set(CourseGlobalSetting.all_course_id())
    optout_receiving_global_course_emails(user, global_course_ids)
    disconnect_third_party_auth(user)
    mask_name(user)
    mask_login_code(user)
    delete_certificates(user)
    mask_shoppingcart_personalinfo(user)
    mask_email(user)


def disable_all_additional_info(user):
    for additional_setting in AdditionalInfoSetting.find_by_user(user):
        additional_setting.value = hash(additional_setting.value)
        additional_setting.save()


def optout_receiving_global_course_emails(user, global_course_ids):
    for global_course_id in global_course_ids:
        optout, _ = Optout.objects.get_or_create(user=user, course_id=global_course_id)
        optout.force_disabled = True
        optout.save()


def mask_name(user):
    hashed_name = hash(user.profile.name)
    for certificate in GeneratedCertificate.objects.filter(user_id=user.id):
        certificate.name = hashed_name
        certificate.save()
    user.profile.name = hashed_name
    user.profile.save()
    # first_name and last_name of User are limited 32 length. Therefore, update to blank.
    user.first_name = ''
    user.last_name = ''
    user.save()


def mask_login_code(user):
    if hasattr(user, 'bizuser'):
        user.bizuser.login_code = get_random_string(30)
        user.bizuser.save()


def mask_email(user):
    hashed_email = hash(user.email + get_random_string(32))
    for cea in CourseEnrollmentAllowed.objects.filter(email=user.email):
        cea.email = hashed_email
        cea.save()
    for mea in ManualEnrollmentAudit.objects.filter(enrolled_email=user.email):
        mea.enrolled_email = hashed_email
        mea.save()
    for pec in PendingEmailChange.objects.filter(user_id=user.id):
        pec.new_email = hashed_email
        pec.save()
    user.email = hashed_email
    user.save()
    # If the user has changed the email address, it has been stored in the meta.
    user.profile.meta = ''
    user.profile.save()


def mask_shoppingcart_personalinfo(user):
    for pis in PersonalInfo.objects.filter(user=user):
        pis.full_name = hash(pis.full_name) if pis.full_name is not None else None
        pis.kana = hash(pis.kana) if pis.kana is not None else None
        pis.postal_code = None
        pis.address_line_1 = hash(pis.address_line_1) if pis.address_line_1 is not None else None
        pis.address_line_2 = hash(pis.address_line_2) if pis.address_line_2 is not None else None
        pis.phone_number = None
        pis.free_entry_field_1 = hash(pis.free_entry_field_1) if pis.free_entry_field_1 is not None else None
        pis.free_entry_field_2 = hash(pis.free_entry_field_2) if pis.free_entry_field_2 is not None else None
        pis.free_entry_field_3 = hash(pis.free_entry_field_3) if pis.free_entry_field_3 is not None else None
        pis.free_entry_field_4 = hash(pis.free_entry_field_4) if pis.free_entry_field_4 is not None else None
        pis.free_entry_field_5 = hash(pis.free_entry_field_5) if pis.free_entry_field_5 is not None else None
        pis.save()


def disconnect_third_party_auth(user):
    for state in pipeline.get_provider_user_states(user):
        strategy = social_utils.load_strategy()
        backend = social_utils.load_backend(strategy, state.provider.backend_name, None)
        backend.disconnect(user=user, association_id=state.association_id)


def delete_certificates(user):
    raises_exception = False
    for certificate in GeneratedCertificate.objects.filter(user_id=user.id):
        # Use username since email may has been already masked.
        CertificatePDF(user.username, certificate.course_id, False, False).delete()
        # Confirm that certificate's status 'downloadable' or 'generating' has changed to 'deleted'.
        if GeneratedCertificate.objects.filter(pk=certificate.id,
                                               status__in=[CertificateStatuses.downloadable, CertificateStatuses.generating]).exists():
            log.error('Failed to delete certificate. user={user_id}, course_id={course_id}'.format(
                user_id=user.id, course_id=certificate.course_id
            ))
            raises_exception = True
    if raises_exception:
        raise Exception('Failed to delete certificates of User {user_id}.'.format(user_id=user.id))


def hash(value):
    """
    Returns hashed value.
    """
    return hmac.new(settings.BIZ_SECRET_KEY.encode('utf-8'), value.encode('utf-8'), hashlib.sha256).hexdigest()
