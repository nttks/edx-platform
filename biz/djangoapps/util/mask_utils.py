"""
Mask methods for working with user objects.
"""

import hashlib
import hmac
import logging

from django.conf import settings
from django.utils.crypto import get_random_string
from social.apps.django_app import utils as social_utils

from bulk_email.models import Optout
from certificates.models import CertificateStatuses, GeneratedCertificate
from student.models import CourseEnrollmentAllowed, ManualEnrollmentAudit, PendingEmailChange
from third_party_auth import pipeline
from pdfgen.certificate import CertificatePDF

log = logging.getLogger(__name__)


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
    for mea in ManualEnrollmentAudit.objects.filter(enrolled_by_id=user.id):
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
