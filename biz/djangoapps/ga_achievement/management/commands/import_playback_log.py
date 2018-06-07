import csv
import logging
import re
import StringIO
import urlparse
from datetime import datetime, timedelta
from optparse import make_option

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.decorators import handle_command_exception
from biz.djangoapps.ga_achievement.log_store import PlaybackLogStore
from openedx.core.djangoapps.ga_operation.utils import open_bucket_from_s3

log = logging.getLogger(__name__)


class Command(BaseCommand):

    help = """
    Usage: python manage.py lms --settings=aws import_playback_log [--target_date=<yyyymmdd>]
    """

    option_list = BaseCommand.option_list + (
        make_option('--target_date',
                    default=None,
                    action='store',
                    help="Import csv-data on yesterday, option target_date for specific date(format:'yyyymmdd')."),
    )

    @handle_command_exception(settings.BIZ_IMPORT_PLAYBACK_LOG_COMMAND_OUTPUT)
    def handle(self, *args, **options):

        if len(args) > 0:
            raise CommandError("This command requires no arguments. Use target_date option if you want.")

        target_date_str = options.get('target_date') or datetime_utils.timezone_yesterday().strftime('%Y%m%d')
        log.info(u"Command import_playback_log, target_date={}".format(target_date_str))
        try:
            target_date = datetime.strptime(target_date_str, '%Y%m%d')
        except ValueError:
            raise CommandError("Option target_date must be 'yyyymmdd' format.")
        log.info("Command import_playback_log started for {}.".format(target_date))

        bucket_name = settings.BIZ_PLAYBACK_LOG_BUCKET_NAME
        key_path = 'playbacklog/{}/mv_play_log_{}.csv'.format(
            target_date.strftime('%Y/%m/%d'),
            target_date.strftime('%Y%m%d')
        )
        def _get_csv_data_as_string():
            with open_bucket_from_s3(bucket_name) as bucket:
                key = bucket.get_key(key_path)
                if key is None:
                    raise Exception("Command import_playback_log can not find csv-file [{}/{}].".format(bucket_name, key_path))
                return key.get_contents_as_string()

        def _validate_and_get_duration(duration):
            # Validate format duration(HH:MM:SS) to get total seconds.
            m = re.match(r'^(?P<hour>[0-9]{2}):(?P<minite>[0-5][0-9]):(?P<second>[0-5][0-9])$', duration)
            return int(timedelta(hours=int(m.group('hour')), minutes=int(m.group('minite')), seconds=int(m.group('second'))).total_seconds()) if m else 0

        PARAMETER_KEYS = [PlaybackLogStore.FIELD_TARGET_ID, PlaybackLogStore.FIELD_COURSE_ID, PlaybackLogStore.FIELD_VERTICAL_ID]
        def _validate_and_get_url_parameter(url_parameter):
            # Validate to have required all parameter keys, and get values.
            parameter = urlparse.parse_qs(url_parameter)
            return {k: parameter[k][0] for k in PARAMETER_KEYS} if all([k in parameter for k in PARAMETER_KEYS]) else None

        COL_INDEX_DURATION = 2
        COL_INDEX_URL_PARAMETER = 5

        aggregate_data = {}
        skip_row_count = 0
        reader = csv.reader(StringIO.StringIO(_get_csv_data_as_string()))
        for row in reader:
            # Skip first line.
            if reader.line_num <= 1:
                continue
            duration = _validate_and_get_duration(row[COL_INDEX_DURATION])
            row_data = _validate_and_get_url_parameter(row[COL_INDEX_URL_PARAMETER])
            if duration == 0 or row_data is None:
                skip_row_count += 1
                continue
            # Make unique-key(temporary) of target_id, course_id and vertical_id to calculate duration.
            _key = PlaybackLogStore.FIELD_DELIMITER.join([row_data[key] for key in PARAMETER_KEYS])
            if _key in aggregate_data:
                aggregate_data[_key][PlaybackLogStore.FIELD_DURATION] += duration
            else:
                aggregate_data[_key] = {
                    PlaybackLogStore.FIELD_COURSE_ID: row_data[PlaybackLogStore.FIELD_COURSE_ID],
                    PlaybackLogStore.FIELD_VERTICAL_ID: row_data[PlaybackLogStore.FIELD_VERTICAL_ID],
                    PlaybackLogStore.FIELD_TARGET_ID: row_data[PlaybackLogStore.FIELD_TARGET_ID],
                    PlaybackLogStore.FIELD_DURATION: duration,
                    PlaybackLogStore.FIELD_CREATED_AT: target_date,
                }

        len_aggregate_data = len(aggregate_data)
        log.info("Command import_playback_log get data from [{}/{}], record count({}), skip row count({}).".format(
            bucket_name, key_path, len_aggregate_data, skip_row_count))

        playback_log = PlaybackLogStore(created_at=target_date)

        playback_log.remove_documents()
        playback_log_count = playback_log.get_count()
        if playback_log_count > 0:
            raise Exception("Command import_playback_log can not remove mongo records of {}, record count({}).".format(
                target_date, playback_log_count))

        log.info("Command import_playback_log removed mongo records of {}.".format(target_date))

        if len_aggregate_data:
            playback_log.set_documents(aggregate_data.values())

            playback_log_count = playback_log.get_count()
            if playback_log_count == len_aggregate_data:
                log.info("Command import_playback_log stored mongo records of {}, record count({}).".format(
                    target_date, playback_log_count))
            else:
                raise Exception("Command import_playback_log can not store mongo records of {}, record count({}), store count({}).".format(
                    target_date, len_aggregate_data, playback_log_count))

            if playback_log.has_duplicate_record():
                raise Exception("Duplicated documents are detected in playback_log.")

        log.info("Command import_playback_log finished for {}.".format(target_date))
