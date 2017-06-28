import argparse
import json
import logging
from optparse import make_option

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from ...models import DiagnosisInfo, GeneratePDFState
from ...pdf import create_pdf
from opaque_keys import InvalidKeyError
from opaque_keys.edx.locator import CourseLocator

log = logging.getLogger(__name__)


def check_course_id(course_id):
    """Check course_id."""
    try:
        CourseLocator.from_string(course_id)
    except InvalidKeyError:
        raise CommandError(
            "'{}' is an invalid course_id".format(course_id)
        )


class Command(BaseCommand):
    help = 'Usage: python manage.py lms --settings=aws ga_diagnosis_generate_pdf <course_id> <username>'

    def add_arguments(self, parser):
        parser.add_argument('args', nargs=argparse.REMAINDER)

    def handle(self, *args, **options):

        if len(args) != 2:
            self.print_help('manage.py', 'ga_diagnosis_generate_pdf')
            raise CommandError('course_id or username is not specified.')

        course_id, username = args
        check_course_id(course_id)
        course_id = CourseLocator.from_string(course_id)
        response = 'PDF file was not generated.'
        try:
            diagnosis_info = DiagnosisInfo.objects.prefetch_related('user').get(
                user=User.objects.get(username=username),
                course_id=course_id
            )
            key = GeneratePDFState.make_hashkey(str(course_id) + username)
            response = create_pdf(diagnosis_info=diagnosis_info, key=key)
            pdf_state, _ = GeneratePDFState.objects.get_or_create(diagnosis_info=diagnosis_info)
            download_url = json.loads(response).get('download_url')
            if download_url:
                pdf_state.status = GeneratePDFState.downloadable
                pdf_state.download_url = download_url
                pdf_state.save()
        except User.DoesNotExist:
            log.error(u'username: {} does not exists'.format(username))
        except DiagnosisInfo.DoesNotExist:
            log.error(u'DiagnosisInfo object was not found: {} does not exists'.format(username))
        except Exception as e:
            log.exception(u'Caught some exception: {}'.format(e))
        log.info(response)
