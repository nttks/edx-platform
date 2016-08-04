"""
Get a course situation data from the MongoDB.
Processed into w2ui data and csv data.
"""
from django.conf import settings

from biz.djangoapps.util.mongo_utils import BizStore


class PlaybackLogStore(BizStore):
    """
    A data store that deals with playback log records
    """

    FIELD_ID = '_id'
    FIELD_COURSE_ID = 'course_id'
    FIELD_TARGET_ID = 'target_id'
    FIELD_VERTICAL_ID = 'vertical_id'
    FIELD_DURATION = 'duration'
    FIELD_CREATED_AT = 'created_at'

    def __init__(self, course_id, target_id):
        """
        Set initial information

        :param course_id: course id
        :param target_id: target id
        """
        key_conditions = {
            self.FIELD_COURSE_ID: course_id,
            self.FIELD_TARGET_ID: target_id,
        }
        super(PlaybackLogStore, self).__init__(settings.BIZ_MONGO['playback_log'], key_conditions)

    def aggregate_duration_by_vertical(self):
        """
        Aggregate the amount of duration by grouping vertical id

        :return: summary dict
            e.g.)
            {
                u'd1f1c0a6d71945e883c539452a6dfb26': 100.0,
                u'ab274f9c70934b018a7170bc4373bde1': 200.0,
                u'0c5a4b6724d74bfeaf9e5cd001c58efc': 300.0,
            }
        """
        return self.aggregate(self.FIELD_VERTICAL_ID, self.FIELD_DURATION)
