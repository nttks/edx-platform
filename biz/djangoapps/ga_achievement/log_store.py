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

    def __init__(self, course_id=None, target_id=None, created_at=None):
        """
        Set initial information

        :param course_id: course id
        :param target_id: target id
        :param created_at: created at
        """
        key_conditions = {}
        if course_id:
            key_conditions[self.FIELD_COURSE_ID] = course_id
        if target_id:
            key_conditions[self.FIELD_TARGET_ID] = target_id
        if created_at:
            key_conditions[self.FIELD_CREATED_AT] = created_at

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

    def aggregate_duration_by_vertical_and_target(self):
        """
        Aggregate the amount of duration by grouping vertical id and target id

        :return: summary dict
            e.g.)
            {
                u'bc023973d2bce92f0ee4368e1ceae671f2ad071ae0e92e5a9e8b2a224460e689@86bcaab2af78478e8a1b5f05dd5b5378': 100.0,
                u'ca42767fa83addcb9f88274fd326bbef4f480b10d77310afae7f967d23bfed5b@2cecf75ed74c4cb6a80f264b7020b490': 200.0,
                u'20ef8b87fc7c29ccdb5e530bd246a82cdc8328aded830f771ffb0794c0193bc9@bd4ffeb869ba437683dc754685eb1ce1': 300.0,
            }
        """
        return self.aggregate_sum(
            [self.FIELD_VERTICAL_ID, self.FIELD_TARGET_ID],
            self.FIELD_DURATION,
        )

    def has_duplicate_record(self):
        return self.has_duplicate([self.FIELD_COURSE_ID, self.FIELD_VERTICAL_ID, self.FIELD_TARGET_ID, self.FIELD_CREATED_AT])
