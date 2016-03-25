"""
Get a course situation data from the MongoDB.
Processed into w2ui data and csv data.
"""
from datetime import datetime
import numbers

from django.conf import settings
from django.utils.translation import ugettext as _

from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.mongo_utils import BizStore, DEFAULT_DATETIME

SCORE_STORE_FIELD_ID = '_id'
SCORE_STORE_FIELD_CONTRACT_ID = 'Contract ID'
SCORE_STORE_FIELD_COURSE_ID = 'Course ID'
SCORE_STORE_FIELD_NAME = 'Full Name'
SCORE_STORE_FIELD_USERNAME = 'Username'
SCORE_STORE_FIELD_EMAIL = 'Email'
SCORE_STORE_FIELD_STUDENT_STATUS = 'Student Status'
SCORE_STORE_FIELD_STUDENT_STATUS_NOT_ENROLLED = 'Not Enrolled'
SCORE_STORE_FIELD_STUDENT_STATUS_ENROLLED = 'Enrolled'
SCORE_STORE_FIELD_STUDENT_STATUS_UNENROLLED = 'Unenrolled'
SCORE_STORE_FIELD_STUDENT_STATUS_DISABLED = 'Disabled'
SCORE_STORE_FIELD_CERTIFICATE_STATUS = 'Certificate Status'
SCORE_STORE_FIELD_CERTIFICATE_STATUS_DOWNLOADABLE = 'Downloadable'
SCORE_STORE_FIELD_CERTIFICATE_STATUS_UNPUBLISHED = 'Unpublished'
SCORE_STORE_FIELD_ENROLL_DATE = 'Enroll Date'
SCORE_STORE_FIELD_CERTIFICATE_ISSUE_DATE = 'Certificate Issue Date'
SCORE_STORE_FIELD_TOTAL_SCORE = 'Total Score'


class ScoreStore(BizStore):
    """
    Dealing with the data required for the output of w2ui and csv.
    """

    def __init__(self, contract_id, course_id):
        """
        set the necessary information

        :param contract_id:  Contract ID
        :param course_id: Course ID
        """
        self._store_config = settings.BIZ_MONGO['score']
        key_conditions = {
            SCORE_STORE_FIELD_CONTRACT_ID: contract_id,
            SCORE_STORE_FIELD_COURSE_ID: course_id,
        }
        key_index_columns = [SCORE_STORE_FIELD_CONTRACT_ID, SCORE_STORE_FIELD_COURSE_ID]
        super(ScoreStore, self).__init__(self._store_config, key_conditions, key_index_columns)

    def get_list(self, conditions={}):
        """
        Get the Mongodb data for screen display

        :param conditions: MongoDB Find Condition for Dict
        :return: data from create_list_for_w2ui()
        """
        excludes = {
            SCORE_STORE_FIELD_ID: False,
            SCORE_STORE_FIELD_CONTRACT_ID: False,
            SCORE_STORE_FIELD_COURSE_ID: False,
        }
        return self.create_list_for_w2ui(self.get_documents(conditions=conditions, excludes=excludes))

    @classmethod
    def create_list_for_w2ui(cls, items):
        """
        Data for creating w2ui

        :param items: Obtained data from mongodb
        :return columns: column(dict) for w2ui
        :return records: contents(list) for w2ui
        :return searches: contents(list) for w2ui
        """
        columns = []
        searches = []
        fields = cls.get_fields(items)
        for field in fields:
            column = {}
            column['attr'] = 'align=center'
            column['field'] = field
            column['caption'] = field
            column['sortable'] = True
            column['hidden'] = False
            column['size'] = '{}%'.format(100 / len(fields))
            if isinstance(items[0][field], numbers.Number):
                column['style'] = 'text-align: right'
            elif isinstance(items[0][field], datetime):
                column['style'] = 'text-align: right'
                column['render'] = 'date:yyyy/mm/dd'
                # make searches
                searches.append({
                    'field': _(field), 'caption': _(field), 'type': 'date'
                })
            else:
                column['style'] = 'text-align: left'
                # make searches
                if field == _(SCORE_STORE_FIELD_STUDENT_STATUS):
                    searches.append({
                        'field': _(SCORE_STORE_FIELD_STUDENT_STATUS),
                        'caption': _(SCORE_STORE_FIELD_STUDENT_STATUS),
                        'type': 'list',
                        'options': {'items': [_('Enrolled'), _('Unenrolled'), _('Disabled')]},
                    })
                elif field == _(SCORE_STORE_FIELD_CERTIFICATE_STATUS):
                    searches.append({
                        'field': _(SCORE_STORE_FIELD_CERTIFICATE_STATUS),
                        'caption': _(SCORE_STORE_FIELD_CERTIFICATE_STATUS),
                        'type': 'list',
                        'options': {'items': [_('Downloadable'), _('Unpublished')]},
                    })
                else:
                    searches.append({'field': _(field), 'caption': _(field), 'type': 'text'})

            columns.append(column)

        records = []
        for i, item in enumerate(items):
            record = {}
            for key, val in item.iteritems():
                if isinstance(val, float):
                    val = str(val * 100) + '%'
                elif isinstance(val, datetime):
                    if val == DEFAULT_DATETIME:
                        val = None
                    else:
                        val = datetime_utils.format_for_w2ui(val)

                record[key] = val
            record['recid'] = i + 1
            records.append(record)

        return columns, records, searches

    def get_csv_list(self, conditions={}):
        """
        Get the MongoDB data for the CSV output

        :param conditions: dict type of find conditions
        :return: data from create_list_for_csv()
        """
        excludes = {
            SCORE_STORE_FIELD_ID: False,
            SCORE_STORE_FIELD_CONTRACT_ID: False,
            SCORE_STORE_FIELD_COURSE_ID: False,
        }
        return self.create_list_for_csv(self.get_documents(conditions=conditions, excludes=excludes))

    @classmethod
    def create_list_for_csv(cls, items):
        """
        Data for creating csv

        :param items: Obtained data from mongodb
        :return columns: list
        :return records: list
        """
        columns = cls.get_fields(items)
        records = []
        for item in items:
            record = []
            for column in columns:
                val = item.get(column, '')
                if isinstance(val, float):
                    val = str(val * 100) + '%'
                elif isinstance(val, datetime):
                    if val == DEFAULT_DATETIME:
                        val = None
                    else:
                        val = datetime_utils.to_jst(val).strftime('%Y/%m/%d')
                record.append(val)
            records.append(record)
        return columns, records
