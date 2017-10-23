# -*- coding: utf-8 -*-
"""
Management command to show a list of enabled contracts.
"""
import logging
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from biz.djangoapps.ga_contract.models import Contract
from biz.djangoapps.util.decorators import handle_command_exception

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Show a list of enabled contracts.
    """
    help = """
    Usage: python manage.py lms --settings=aws show_enabled_contract [--debug] [--excludes=<exclude_ids>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--debug',
                    default=False,
                    action='store_true',
                    help='Use debug log'),
        make_option('--excludes',
                    default=None,
                    action='store',
                    help='Specify contract ids to exclude as comma-delimited integers (like 1 or 1,2)'),
    )

    @handle_command_exception(settings.BIZ_SET_SHOW_ENABLED_CONTRACT_COMMAND_OUTPUT, True)
    def handle(self, *args, **options):

        debug = options.get('debug')
        if debug:
            stream = logging.StreamHandler(self.stdout)
            log.addHandler(stream)
            log.setLevel(logging.DEBUG)
        exclude_ids = options.get('excludes') or []
        if exclude_ids:
            try:
                exclude_ids = map(int, exclude_ids.split(','))
            except ValueError:
                raise CommandError("excludes should be specified as comma-delimited integers (like 1 or 1,2).")
        log.debug(u"exclude_ids={}".format(exclude_ids))

        contracts = Contract.objects.enabled(days_after=-1).all().exclude(id__in=exclude_ids).order_by('id')

        c = ','.join([str(contract.id) for contract in contracts])
        log.debug(u"contract_ids=[{}]".format(c))

        return u"ContractID {}".format(c)
