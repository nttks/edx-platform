"""Certificates API for gacco"""
import hashlib
import logging

from django.conf import settings
from django.utils.translation import ugettext as _

from certificates.models import CertificateStatuses, GeneratedCertificate
from openedx.core.djangoapps.ga_self_paced import api as self_paced_api
from openedx.core.djangoapps.ga_task.api import submit_task, AlreadyRunningError
from pdfgen.tasks import self_generate_certificate
from student.models import CourseEnrollment

log = logging.getLogger(__name__)


def generate_user_certificate(request, student, course):
    """
    Submits a task to self-generate a certificate for a given student enrolled in the self-paced course
    """
    # Check if the course is set as self-paced
    if not course.self_paced:
        success = False
        message = "Couldn't submit a certificate self-generation task because the course is not self-paced."
        log.warning(
            "{message} course={course_id}, user={user_id}".format(
                message=message, course_id=unicode(course.id), user_id=student.id)
        )
        _save_cert_status_as_error(student, course, "This course is not self-paced.")
        return {
            'success': success,
            'message': message,
        }

    # Check if student's enrollment has not expired yet
    enrollment = CourseEnrollment.get_enrollment(student, course.id)
    if self_paced_api.is_course_closed(enrollment):
        success = False
        message = "Couldn't submit a certificate self-generation task because student's enrollment has already expired."
        log.warning(
            "{message} course={course_id}, user={user_id}".format(
                message=message, course_id=unicode(course.id), user_id=student.id)
        )
        _save_cert_status_as_error(student, course, "Student's enrollment has already expired")
        return {
            'success': success,
            'message': message,
        }

    # Check if cert status has not created yet
    if GeneratedCertificate.objects.filter(course_id=course.id, user=student).exists():
        success = False
        message = "Couldn't submit a certificate self-generation task because certificate status has already created."
        log.warning(
            "{message} course={course_id}, user={user_id}".format(
                message=message, course_id=unicode(course.id), user_id=student.id)
        )
        return {
            'success': success,
            'message': message,
        }

    task_type = 'self_generate_certificate'
    task_class = self_generate_certificate
    task_input = {
        'course_id': unicode(course.id),
        'student_ids': [student.id],
    }
    task_key = hashlib.md5('{course}_{student}'.format(course=unicode(course.id), student=student.id)).hexdigest()
    queue = settings.PDFGEN_CELERY_DEFAULT_QUEUE
    try:
        task = submit_task(request, task_type, task_class, task_input, task_key, queue)
    except AlreadyRunningError:
        success = False
        message = _("Task is already running.")
        log.warning(
            "Certificate self-generation task is submitted, but the task is already running. "
            "course={course_id}, user={user_id}".format(
                course_id=unicode(course.id), user_id=student.id)
        )
    except Exception as e:
        success = False
        message = _("An unexpected error occurred.")
        log.exception(
            "Unexpected error occurred while submitting certificate self-generation task. "
            "course={course_id}, user={user_id}".format(
                course_id=unicode(course.id), user_id=student.id)
        )
        _save_cert_status_as_error(student, course, str(e))
    else:
        success = True
        message = "Certificate self-generation task(task_id={task_id}) has been started.".format(task_id=task.id)

    return {
        'success': success,
        'message': message,
    }


def _save_cert_status_as_error(student, course, error_reason):
    """
    Save cert.status as error if not exists
    """
    cert, created = GeneratedCertificate.objects.get_or_create(user=student, course_id=course.id)
    if created:
        cert.course_id = course.id
        cert.user = student
        cert.status = CertificateStatuses.error
        cert.error_reason = error_reason[:GeneratedCertificate._meta.get_field('error_reason').max_length]
        cert.save()
