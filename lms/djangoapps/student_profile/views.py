""" Views for a student's profile information. """

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django_countries import countries

from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.views.decorators.http import require_http_methods

from biz.djangoapps.ga_contract.models import ContractDetail
from certificates.models import (
    GeneratedCertificate, CertificateStatuses, CertificatesOnUserProfile,
    certificate_status_for_student
)
from edxmako.shortcuts import render_to_response
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.ga_operation.utils import course_filename, handle_file_from_s3
from openedx.core.djangoapps.user_api.accounts.api import get_account_settings
from openedx.core.djangoapps.user_api.accounts.serializers import PROFILE_IMAGE_KEY_PREFIX
from openedx.core.djangoapps.user_api.errors import UserNotFound, UserNotAuthorized
from openedx.core.djangoapps.user_api.preferences.api import get_user_preferences
from student.models import User, CourseEnrollment
from microsite_configuration import microsite
from xmodule.modulestore.django import modulestore


@login_required
@require_http_methods(['GET'])
def learner_profile(request, username):
    """Render the profile page for the specified username.

    Args:
        request (HttpRequest)
        username (str): username of user whose profile is requested.

    Returns:
        HttpResponse: 200 if the page was sent successfully
        HttpResponse: 302 if not logged in (redirect to login page)
        HttpResponse: 405 if using an unsupported HTTP method
    Raises:
        Http404: 404 if the specified user is not authorized or does not exist

    Example usage:
        GET /account/profile
    """
    try:
        return render_to_response(
            'student_profile/learner_profile.html',
            learner_profile_context(request, username, request.user.is_staff)
        )
    except (UserNotAuthorized, UserNotFound, ObjectDoesNotExist):
        raise Http404


def learner_profile_context(request, profile_username, user_is_staff):
    """Context for the learner profile page.

    Args:
        logged_in_user (object): Logged In user.
        profile_username (str): username of user whose profile is requested.
        user_is_staff (bool): Logged In user has staff access.
        build_absolute_uri_func ():

    Returns:
        dict

    Raises:
        ObjectDoesNotExist: the specified profile_username does not exist.
    """
    profile_user = User.objects.get(username=profile_username)
    logged_in_user = request.user

    own_profile = (logged_in_user.username == profile_username)

    account_settings_data = get_account_settings(request, profile_username)

    preferences_data = get_user_preferences(profile_user, profile_username)

    if own_profile or preferences_data.get('account_privacy', '') == 'all_users':
        cert_infos = _get_cert_infos(profile_user, own_profile)
    else:
        cert_infos = []

    context = {
        'data': {
            'profile_user_id': profile_user.id,
            'default_public_account_fields': settings.ACCOUNT_VISIBILITY_CONFIGURATION['public_fields'],
            'default_visibility': settings.ACCOUNT_VISIBILITY_CONFIGURATION['default_visibility'],
            'accounts_api_url': reverse("accounts_api", kwargs={'username': profile_username}),
            'preferences_api_url': reverse('preferences_api', kwargs={'username': profile_username}),
            'preferences_data': preferences_data,
            'account_settings_data': account_settings_data,
            'profile_image_upload_url': reverse('profile_image_upload', kwargs={'username': profile_username}),
            'profile_image_remove_url': reverse('profile_image_remove', kwargs={'username': profile_username}),
            'profile_image_max_bytes': settings.PROFILE_IMAGE_MAX_BYTES,
            'profile_image_min_bytes': settings.PROFILE_IMAGE_MIN_BYTES,
            'account_settings_page_url': reverse('account_settings'),
            'has_preferences_access': (logged_in_user.username == profile_username or user_is_staff),
            'own_profile': own_profile,
            'country_options': list(countries),
            'language_options': settings.ALL_LANGUAGES,
            'platform_name': microsite.get_value('platform_name', settings.PLATFORM_NAME),
            'parental_consent_age_limit': settings.PARENTAL_CONSENT_AGE_LIMIT,
            'cert_infos': cert_infos,
        },
        'disable_courseware_js': True,
    }
    return context


def _get_cert_infos(user, own_profile):
    generated_certificates = GeneratedCertificate.objects.filter(user=user).order_by('-created_date')

    cert_infos = []
    for generated_certificate in generated_certificates:
        course_key = CourseKey.from_string(str(generated_certificate.course_id))

        if _is_hidden_course(course_key):
            continue

        course_enrollment = CourseEnrollment.get_enrollment(user, course_key)
        if course_enrollment is None:
            continue

        cert_status = certificate_status_for_student(user, generated_certificate.course_id)
        if cert_status['status'] == CertificateStatuses.downloadable:

            cert_status['course_id_str'] = str(generated_certificate.course_id)
            cert_status['course_name'] = course_enrollment.course_overview.display_name_with_default
            cert_status['image_url'] = _get_thumbnail_url(course_key)

            is_visible_to_public = _is_certificate_visible_to_public(user, generated_certificate.course_id)

            if own_profile:
                cert_status['is_visible_to_public'] = is_visible_to_public
                cert_infos.append(cert_status)
            else:
                if is_visible_to_public:
                    # delete from the viewpoint of protection of personal information
                    # (The real name is printed on the certificate)
                    del cert_status['download_url']

                    cert_infos.append(cert_status)

    return cert_infos


def _is_hidden_course(course_key):
    course = modulestore().get_course(course_key)

    if course is None:
        return True

    if course.course_category is None:
        return True

    if 'gacco' not in course.course_category:
        return True

    return False


def _get_thumbnail_url(course_key):
    _bucket_name = settings.PDFGEN_BASE_BUCKET_NAME
    _key_prefix = 'thumbnail-'
    s3_handle = handle_file_from_s3(
        '{}{}.jpg'.format(_key_prefix, course_filename(course_key)),
        _bucket_name
    )
    if s3_handle is None:
        return ''
    return s3_handle.generate_url(expires_in=300)


def _is_certificate_visible_to_public(user, course_id):
    try:
        return CertificatesOnUserProfile.objects.get(
            user=user,
            course_id=course_id,
        ).is_visible_to_public
    except CertificatesOnUserProfile.DoesNotExist:
        return False


@login_required
@require_http_methods(['POST'])
def change_visibility_certificates(request, course_id):
    """Handle visibility change requests.

    Args:
        request (HttpRequest)
        course_id (str): course_id of certificate to be changed visibility .

    Returns:
        HttpResponse: 200 if the page was sent successfully
        HttpResponse: 302 if not logged in (redirect to login page)
        HttpResponse: 405 if using an unsupported HTTP method
    Raises:
        HttpResponseBadRequest: if the parameter of is_visible_to_public does not exist
        HttpResponseServerError: if error occurs when saving model

    """
    is_visible_to_public = request.POST.get('is_visible_to_public')
    if is_visible_to_public is not None:
        try:
            cert, __ = CertificatesOnUserProfile.objects.get_or_create(
                user=request.user,
                course_id=CourseKey.from_string(course_id),
            )
            cert.is_visible_to_public = True if (is_visible_to_public == '1') else False
            cert.save()
        except:
            return HttpResponseServerError('Failed to save certifications visibility')

        return HttpResponse(status=200)
    else:
        return HttpResponseBadRequest('There is no is_visible_to_public parameter')
