import logging
from collections import Counter
from datetime import datetime, timedelta
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.biz_mongo_connection import BizMongoConnection
from biz.djangoapps.util.decorators import handle_command_exception

log = logging.getLogger(__name__)


class Command(BaseCommand):
    help = """
    Usage: python manage.py lms --settings=aws check_playback_log [--target_date=<yyyymmdd>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--target_date',
                    default=None,
                    action='store',
                    help="target_date should be 'yyyymmdd' format."),
    )

    @handle_command_exception('/edx/var/log/biz/check_playback_log_command.txt')
    def handle(self, *args, **options):

        if len(args) > 0:
            raise CommandError("This command requires no arguments. Use target_date option if you want.")

        target_date = options.get('target_date')
        if target_date:
            try:
                target_date = datetime.strptime(target_date, '%Y%m%d')
            except ValueError:
                raise CommandError("target_date should be 'yyyymmdd' format.")
        else:
            # By default, check for today (JST)
            target_date = datetime_utils.timezone_today()

        log.info("Command check_playback_log started for {}.".format(target_date.strftime('%Y/%m/%d')))

        # NOTE: By default, PyMongo deals with only naive datetimes.
        # NOTE: emr_aggregate_playback_log sets `created_at` to yesterday's midnight.
        #       For example, when it runs at 2017-11-13 06:06:07+9:00, it sets as below:
        #           - u'created_at': datetime.datetime(2017, 11, 12, 0, 0, tzinfo=<bson.tz_util.FixedOffset object>)
        target_datetime = datetime.combine(target_date + timedelta(days=-1), datetime.min.time())

        try:
            store_config = settings.BIZ_MONGO['playback_log']
            db_connection = BizMongoConnection(**store_config)
            db = db_connection.database
            collection = db[store_config['collection']]
        except Exception as e:
            raise e

        try:
            result = collection.aggregate([
                {'$group': {
                    '_id': {
                        'course_id': '$course_id',
                        'vertical_id': '$vertical_id',
                        'target_id': '$target_id',
                        'created_at': '$created_at',
                    },
                    'total': {'$sum': 1},
                }},
                {'$match': {
                    '_id.created_at': target_datetime,
                    'total': {'$gt': 1},
                }},
            ],
                allowDiskUse=True,
            )['result']

        except Exception as e:
            raise e

        if result:
            messages = ["{} duplicated documents are detected in playback_log for {}.".format(len(result), target_date.strftime('%Y/%m/%d'))]
            for course_id, count in Counter([x['_id']['course_id'] for x in result]).most_common():
                messages.append('{},{}'.format(course_id, count))
            raise Exception('\n'.join(messages))
