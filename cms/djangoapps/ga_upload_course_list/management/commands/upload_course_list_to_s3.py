"""Django management command to force certificate generation"""
from optparse import make_option

from django.core.management.base import BaseCommand

from ga_upload_course_list.views import CourseList


class Command(BaseCommand):
    args = ""
    help = """Upload course template list with course card."""

    option_list = BaseCommand.option_list + (
        make_option(
            '-t', '--template-only',
            action="store_true",
            dest='template_only',
            default=False,
            help='Upload only template'),
        make_option(
            '-c', '--category',
            dest='category',
            default=None,
            help='Filter by course category')
    )

    def handle(self, *args, **options):
        template_only = options['template_only']
        category = options['category']

        course_list = CourseList(target_category=category)
        course_list.upload(template_only)
