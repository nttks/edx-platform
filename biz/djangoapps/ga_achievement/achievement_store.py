# -*- coding: utf-8 -*-
"""
Get a course situation data from the MongoDB.
Processed into w2ui data and csv data.
"""
from collections import OrderedDict
from datetime import datetime
import numbers

from django.conf import settings
from django.utils.translation import ugettext as _

from biz.djangoapps.util import datetime_utils
from biz.djangoapps.util.mongo_utils import BizStore, DEFAULT_DATETIME


class AchievementStoreBase(BizStore):
    """
    A base class of data store that deals with status records
    """

    FIELD_ID = '_id'
    FIELD_CONTRACT_ID = 'contract_id'
    FIELD_COURSE_ID = 'course_id'
    FIELD_DOCUMENT_TYPE = 'document_type'
    FIELD_DOCUMENT_TYPE__COLUMN = 'column'
    FIELD_DOCUMENT_TYPE__RECORD = 'record'
    FIELD_LOGIN_CODE = 'Login Code'
    FIELD_FULL_NAME = 'Full Name'
    FIELD_USERNAME = 'Username'
    FIELD_EMAIL = 'Email'
    FIELD_ADDITIONAL_INFO = 'Additional Info'
    FIELD_STUDENT_STATUS = 'Student Status'
    FIELD_STUDENT_STATUS__NOT_ENROLLED = 'Not Enrolled'
    FIELD_STUDENT_STATUS__ENROLLED = 'Enrolled'
    FIELD_STUDENT_STATUS__UNENROLLED = 'Unenrolled'
    FIELD_STUDENT_STATUS__DISABLED = 'Disabled'
    FIELD_STUDENT_STATUS__EXPIRED = 'Expired'
    COLUMN_TYPE__TEXT = 'text'
    COLUMN_TYPE__DATE = 'date'
    COLUMN_TYPE__TIME = 'time'
    COLUMN_TYPE__PERCENT = 'percent'
    VALUE__NOT_ATTEMPTED = u'―'  # U+2015

    def __init__(self, store_config, contract_id, course_id):
        """
        Set initial information

        :param contract_id:  Contract ID
        :param course_id: Course ID
        """
        key_conditions = {
            self.FIELD_CONTRACT_ID: contract_id,
            self.FIELD_COURSE_ID: course_id,
        }
        key_index_columns = [
            self.FIELD_CONTRACT_ID,
            self.FIELD_COURSE_ID,
            self.FIELD_DOCUMENT_TYPE,
        ]
        super(AchievementStoreBase, self).__init__(store_config, key_conditions, key_index_columns)

    def get_column_document(self):
        """
        Get stored document which type is marked as 'column'

        :return: a document for column
            e.g.)
            OrderedDict([
                (u'\u6c0f\u540d', u'text'),
                (u'\u30e6\u30fc\u30b6\u30fc\u540d', u'text'),
                (u'\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9', u'text'),
                :
            ])
        """
        conditions = {
            self.FIELD_DOCUMENT_TYPE: self.FIELD_DOCUMENT_TYPE__COLUMN,
        }
        excludes = [
            self.FIELD_ID,
            self.FIELD_CONTRACT_ID,
            self.FIELD_COURSE_ID,
            self.FIELD_DOCUMENT_TYPE,
        ]
        return self.get_document(conditions=conditions, excludes=excludes)

    def get_record_document_by_username(self, username):
        """
        Retrieve stored document which is matched to the given username

        :return: a document for record
            e.g.)
            OrderedDict([
                (u'\u6c0f\u540d', u'\u30c6\u30b9\u30c8\u30e6\u30fc\u30b6\u30fc1'),
                (u'\u30e6\u30fc\u30b6\u30fc\u540d', u'testuser1'),
                (u'\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9', u'testuser1@example.com'),
                :
            ]),
        """
        conditions = {
            self.FIELD_DOCUMENT_TYPE: self.FIELD_DOCUMENT_TYPE__RECORD,
            _(self.FIELD_USERNAME): username,
        }
        excludes = [
            self.FIELD_ID,
            self.FIELD_CONTRACT_ID,
            self.FIELD_COURSE_ID,
            self.FIELD_DOCUMENT_TYPE,
        ]
        return self.get_document(conditions=conditions, excludes=excludes)

    def get_record_documents(self, offset=0, limit=0):
        """
        Get stored documents which type is marked as 'record'

        :param offset: Offset to documents
        :param limit: Limit to documents (A limit() value of 0 (i.e. .limit(0)) is equivalent to setting no limit.)
        :return: documents for record
            e.g.)
            [
                OrderedDict([
                    (u'\u6c0f\u540d', u'\u30c6\u30b9\u30c8\u30e6\u30fc\u30b6\u30fc1'),
                    (u'\u30e6\u30fc\u30b6\u30fc\u540d', u'testuser1'),
                    (u'\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9', u'testuser1@example.com'),
                    :
                ]),
                OrderedDict([...]),
                OrderedDict([...]),
                :
            ]
        """
        conditions = {
            self.FIELD_DOCUMENT_TYPE: self.FIELD_DOCUMENT_TYPE__RECORD,
        }
        excludes = [
            self.FIELD_ID,
            self.FIELD_CONTRACT_ID,
            self.FIELD_COURSE_ID,
            self.FIELD_DOCUMENT_TYPE,
        ]
        return self.get_documents(conditions=conditions, excludes=excludes, offset=offset, limit=limit)

    def get_data_for_w2ui(self, offset=0, limit=0):
        """
        Get data for w2ui grid

        :param offset: Offset to documents
        :param limit: Limit to documents (A limit() value of 0 (i.e. .limit(0)) is equivalent to setting no limit.)
        :return: data for w2ui grid
            e.g.)
            [
                (u'\u6c0f\u540d', u'text'),
                (u'\u30e6\u30fc\u30b6\u30fc\u540d', u'text'),
                (u'\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9', u'text'),
                :
            ],
            [
                OrderedDict([
                    (u'\u6c0f\u540d', u'\u30c6\u30b9\u30c8\u30e6\u30fc\u30b6\u30fc1'),
                    (u'\u30e6\u30fc\u30b6\u30fc\u540d', u'testuser1'),
                    (u'\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9', u'testuser1@example.com'),
                    :
                    ('recid', 1)
                ]),
                OrderedDict([...]),
                OrderedDict([...]),
                :
            ]
        """
        column_document = self.get_column_document()
        record_documents = self.get_record_documents(offset=offset, limit=limit)

        # Note: json.dumps() of views.py converts OrderedDict into dict (it's orderless!), so items() here.
        columns = column_document.items() if column_document is not None else []

        for i, record_document in enumerate(record_documents):
            # Note: w2ui needs 'recid' for each record
            record_document['recid'] = i + 1
            for k, v in record_document.iteritems():
                column_type = column_document.get(k)
                if column_type == self.COLUMN_TYPE__DATE and isinstance(v, datetime):
                    if v == DEFAULT_DATETIME:
                        # Note: This value is used to define the type for 'date' (used only in score status)
                        record_document[k] = None
                    else:
                        # Note: Format to date string with timezone which can be parsed in w2ui
                        record_document[k] = datetime_utils.format_for_w2ui(v)
        return columns, record_documents

    def get_data_for_csv(self):
        """
        Get data for csv download

        :return: data for csv download
            e.g.)
            [
                u'\u6c0f\u540d',
                u'\u30e6\u30fc\u30b6\u30fc\u540d',
                u'\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9',
                    :
            ],
            [
                [u'\u30c6\u30b9\u30c8\u30e6\u30fc\u30b6\u30fc1', u'testuser1', u'testuser1@example.com', ...],
                [u'\u30c6\u30b9\u30c8\u30e6\u30fc\u30b6\u30fc2', u'testuser2', u'testuser2@example.com', ...],
                [u'\u30c6\u30b9\u30c8\u30e6\u30fc\u30b6\u30fc3', u'testuser3', u'testuser3@example.com', ...],
                    :
            ]
        """
        column_document = self.get_column_document()
        record_documents = self.get_record_documents()

        columns = column_document.keys() if column_document is not None else []
        records = []
        for record_document in record_documents:
            record = []
            for k, v in record_document.iteritems():
                column_type = column_document.get(k)
                if column_type == self.COLUMN_TYPE__TEXT:
                    if isinstance(v, basestring):
                        record.append(v)
                    else:
                        record.append('')
                elif column_type == self.COLUMN_TYPE__DATE:
                    if isinstance(v, datetime):
                        if v == DEFAULT_DATETIME:
                            # Note: This value is used to define the type for 'date' (used only in score status)
                            record.append('')
                        else:
                            # Change timezone to JST
                            record.append(datetime_utils.to_jst(v).strftime('%Y/%m/%d'))
                    else:
                        record.append('')
                elif column_type == self.COLUMN_TYPE__TIME:
                    if isinstance(v, numbers.Number):
                        # Convert seconds to 'h:mm' format
                        record.append(datetime_utils.seconds_to_time_format(v))
                    else:
                        record.append('0:00')
                elif column_type == self.COLUMN_TYPE__PERCENT:
                    if v == self.VALUE__NOT_ATTEMPTED:
                        # Note: '―'(U+2015) means 'Not Attempted' (#1816)
                        record.append(v)
                    elif isinstance(v, float):
                        record.append('{:.01%}'.format(v))
                    else:
                        record.append('')
            records.append(record)
        return columns, records

    def get_record_count(self):
        """
        Get stored documents count

        :return: documents count
        """
        conditions = {
            self.FIELD_DOCUMENT_TYPE: self.FIELD_DOCUMENT_TYPE__RECORD,
        }
        return self.get_count(conditions=conditions)


class ScoreStore(AchievementStoreBase):
    """
    A data store that deals with score status records
    """

    FIELD_CONTRACT_ID = 'Contract ID'
    FIELD_COURSE_ID = 'Course ID'

    FIELD_CERTIFICATE_STATUS = 'Certificate Status'
    FIELD_CERTIFICATE_STATUS__DOWNLOADABLE = 'Downloadable'
    FIELD_CERTIFICATE_STATUS__UNPUBLISHED = 'Unpublished'
    FIELD_ENROLL_DATE = 'Enroll Date'
    FIELD_EXPIRE_DATE = 'Expire Date'
    FIELD_CERTIFICATE_ISSUE_DATE = 'Certificate Issue Date'
    FIELD_TOTAL_SCORE = 'Total Score'

    def __init__(self, contract_id, course_id):
        super(ScoreStore, self).__init__(
            settings.BIZ_MONGO['score'],
            contract_id,
            course_id
        )

    def get_column_document(self):
        """
        Get a data set for column (which type is estimated by its value)

        :return: a data set for column
        """
        # For backward compatibility
        column_document = super(ScoreStore, self).get_column_document()
        if column_document:
            return column_document

        excludes = [
            self.FIELD_ID,
            self.FIELD_CONTRACT_ID,
            self.FIELD_COURSE_ID,
        ]
        record_document = self.get_document(excludes=excludes)

        ordered = OrderedDict()
        if record_document is None:
            return ordered

        for k, v in record_document.iteritems():
            if isinstance(v, datetime):
                ordered[k] = self.COLUMN_TYPE__DATE
            elif isinstance(v, float):
                ordered[k] = self.COLUMN_TYPE__PERCENT
            else:
                ordered[k] = self.COLUMN_TYPE__TEXT
        return ordered

    def get_record_documents(self, offset=0, limit=0):
        """
        Get stored documents which type is marked as 'record'

        :param offset: Offset to documents
        :param limit: Limit to documents (A limit() value of 0 (i.e. .limit(0)) is equivalent to setting no limit.)
        :return: documents for record
        """
        # For backward compatibility
        record_documents = super(ScoreStore, self).get_record_documents(offset=offset, limit=limit)
        if record_documents:
            return record_documents

        excludes = [
            self.FIELD_ID,
            self.FIELD_CONTRACT_ID,
            self.FIELD_COURSE_ID,
        ]
        return self.get_documents(excludes=excludes, offset=offset, limit=limit)

    def get_record_count(self):
        """
        Get stored documents count

        :return: documents count
        """
        # For backward compatibility
        record_count = super(ScoreStore, self).get_record_count()
        if record_count:
            return record_count

        return self.get_count()


class PlaybackStore(AchievementStoreBase):
    """
    A data store that deals with playback status records
    """

    FIELD_TOTAL_PLAYBACK_TIME = 'Total Playback Time'
    FIELD_SECTION_PLAYBACK_TIME = 'Section Playback Time'

    def __init__(self, contract_id, course_id):
        super(PlaybackStore, self).__init__(
            settings.BIZ_MONGO['playback'],
            contract_id,
            course_id
        )
