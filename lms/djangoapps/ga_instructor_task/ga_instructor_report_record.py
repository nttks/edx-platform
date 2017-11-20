# -*- coding: utf-8 -*-
"""
gacco's report record for instructor task
"""


class GaInstructorTaskReportRecordBase(dict):
    FIELD_DELIMITER = '___'

    FIELD_COURSE_ID = 'Course ID'

    FIELD_USERNAME = 'Username'
    FIELD_EMAIL = 'Email'
    FIELD_GLOBAL_STAFF = 'Global Staff'
    FIELD_COURSE_ADMIN = 'Admin'
    FIELD_COURSE_STAFF = 'Staff'

    FIELD_ENROLL_STATUS = 'Student Status'
    FIELD_ENROLL_DATE = 'Enroll Date'
    FIELD_RESIGN_STATUS = 'Resign Status'
    FIELD_RESIGN_DATE = 'Resign Date'

    def __init__(self, *args, **kwargs):
        super(GaInstructorTaskReportRecordBase, self).__init__(*args, **kwargs)


class GaScoreDetailReportRecord(GaInstructorTaskReportRecordBase):
    """
    A data store that deals with score detail records
    """

    FIELD_TOTAL_SCORE = 'Total Score'


class GaPlaybackStatusReportRecord(GaInstructorTaskReportRecordBase):
    """
    A data store that deals with playback status records
    """

    FIELD_TOTAL_PLAYBACK_TIME = 'Total Playback Time'
    FIELD_SECTION_PLAYBACK_TIME = 'Section Playback Time'
