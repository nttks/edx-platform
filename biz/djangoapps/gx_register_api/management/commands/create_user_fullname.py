"""
Management command to generate a report
of register user count for biz students each contract.
"""
import logging

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    I will do create user with full name
    Example:
    python manage.py lms --settings=aws create_uer_fullname -u username -p password -e email -f first_name -l last_name
    """

    def add_arguments(self, parser):
        parser.add_argument('-u', nargs='?', help='username', required=True)
        parser.add_argument('-p', nargs='?', help='password', required=True)
        parser.add_argument('-e', nargs='?', help='email', required=True)
        parser.add_argument('-f', nargs='?', help='first_name', required=True)
        parser.add_argument('-l', nargs='?', help='last_name', required=True)

    def handle(self, *args, **options):
        if User.objects.filter(username=options['u']).exists():
            raise ValueError("User already exists")

        user = User.objects.create_user(options['u'], options['e'], options['p'])
        user.first_name = options['f']
        user.last_name = options['l']
        user.save()

