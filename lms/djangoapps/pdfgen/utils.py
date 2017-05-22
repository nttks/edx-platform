import tempfile

from django.conf import settings

from util.file import course_filename_prefix_generator


def get_file_from_s3(key_name, bucket_name=None):
    """
    Returns temporary file created from S3 object by specified key_name.
    """
    from openedx.core.djangoapps.ga_operation.utils import open_bucket_from_s3

    if bucket_name is None:
        bucket_name = settings.PDFGEN_BASE_BUCKET_NAME

    with open_bucket_from_s3(bucket_name) as bucket:
        key = bucket.get_key(key_name)
        if key and key.exists():
            temp_file = tempfile.TemporaryFile()
            key.get_contents_to_file(temp_file)
            temp_file.seek(0)
            return temp_file
        else:
            # specified key does not found on S3
            return None


def course_filename(course_key):
    return course_filename_prefix_generator(course_key, '-')
