import logging
from time import time

from django.contrib.auth.models import User

from certificates.api import emit_certificate_event
from certificates.models import CertificateStatuses, GeneratedCertificate
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.ga_task.models import Task
from openedx.core.djangoapps.ga_task.task import TaskProgress
from pdfgen.certificate import CertificatePDF

log = logging.getLogger(__name__)


def perform_delegate_create_and_publish_certificates(entry_id, task_input, action_name):
    """
    Executes to create and publish a certificate for given students.
    """
    start_time = time()

    entry = Task.objects.get(pk=entry_id)
    course_id = task_input.get('course_id', None)
    course_key = CourseKey.from_string(course_id)
    student_ids = task_input.get('student_ids', [])
    students = User.objects.filter(pk__in=student_ids)

    task_progress = TaskProgress(action_name, len(students), start_time)
    for student in students:
        try:
            task_progress.attempt()
            current_step = {'step': 'Creating Certificate'}
            task_progress.update_task_state(extra_meta=current_step)
            certpdf = CertificatePDF(student.username, course_key, False, False, '', None)
            certpdf.create()
            # Emit tracking
            cert = GeneratedCertificate.objects.get(user=student, course_id=course_key)
            emit_certificate_event('created', student, course_key, event_data={
                'user_id': student.id,
                'course_id': course_id,
                'certificate_id': cert.verify_uuid,
                'enrollment_mode': cert.mode,
                'generation_mode': 'self',
            })

            current_step = {'step': 'Publishing Certificate'}
            task_progress.update_task_state(extra_meta=current_step)
            certpdf.publish()

            cert = GeneratedCertificate.objects.get(user=student, course_id=course_key)
            if cert.status == CertificateStatuses.downloadable:
                log.info(
                    "Task(id={task_id}): "
                    "Finished a certificate self-generation task for user(id={user_id}) in {course_id}.".format(
                        task_id=entry.id, user_id=student.id, course_id=course_id)
                )
                task_progress.success()
            else:
                log.error(
                    "Task(id={task_id}): "
                    "Failed to finish a certificate self-generation task for user(id={user_id}) in {course_id} "
                    "because the status of certificate is not downloadable. status={status}".format(
                        task_id=entry.id, user_id=student.id, course_id=course_id, status=cert.status)
                )
                task_progress.fail()
        except Exception as e:
            log.exception(
                "Task(id={task_id}): "
                "Failed to finish a certificate self-generation task for user(id={user_id}) in {course_id} "
                "because of an unexpected error.".format(
                    task_id=entry.id, user_id=student.id, course_id=course_id)
            )
            task_progress.fail()
            cert, _ = GeneratedCertificate.objects.get_or_create(user=student, course_id=course_key)
            cert.course_id = course_id
            cert.user = student
            cert.status = CertificateStatuses.error
            cert.error_reason = str(e)[:GeneratedCertificate._meta.get_field('error_reason').max_length]
            cert.save()

    return task_progress.update_task_state()
