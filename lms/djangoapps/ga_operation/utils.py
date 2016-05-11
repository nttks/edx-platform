# -*- coding: utf-8 -*-
import os
import logging
import json
from datetime import datetime
from contextlib import contextmanager
from exceptions import OSError

from django.conf import settings
from django.http import HttpResponse

from util.json_request import JsonResponse
from boto.s3.connection import S3Connection
from boto.exception import S3ResponseError
from boto.s3.key import Key
from bson import ObjectId

log = logging.getLogger(__name__)


def get_s3_bucket(conn, bucket_name):
    """Return AWS S3 Bucket Object"""
    try:
        bucket = conn.get_bucket(bucket_name)
    except S3ResponseError:
        bucket = conn.create_bucket(bucket_name)
    return bucket


def get_s3_connection():
    """Return AWS S3 Connection Object"""
    return S3Connection(settings.AWS_ACCESS_KEY_ID, settings.AWS_SECRET_ACCESS_KEY)


def handle_downloaded_file_from_s3(file_name_list, bucket_name):
    """Download files from AWS S3 and mount to the disk."""
    conn = None
    try:
        conn = get_s3_connection()
        bucket = get_s3_bucket(conn, bucket_name)
        for key_name in file_name_list:
            key = bucket.get_key(key_name)
            if not key.exists():
                raise Exception("File:{} was not found from AWS S3.".format(key.name))
            else:
                if not os.path.exists(settings.PDFGEN_BASE_PDF_DIR):
                    os.mkdir(settings.PDFGEN_BASE_PDF_DIR)
                key.get_contents_to_filename(settings.PDFGEN_BASE_PDF_DIR + "/" + key.name)
    finally:
        if conn:
            conn.close()


def handle_uploaded_file_to_s3(form, file_name_keys, bucket_name):
    """Send received files to AWS S3"""
    file_name_list = []
    conn = None
    try:
        conn = get_s3_connection()
        bucket = get_s3_bucket(conn, bucket_name)
        for k in file_name_keys:
            file_data = form.cleaned_data[k]
            f_s3 = Key(bucket)
            f_s3.key = file_data.name
            f_s3.set_contents_from_file(file_data)
            file_name_list.append(file_data.name)
    finally:
        if conn:
            conn.close()
    return file_name_list


def delete_files(file_name_list, base_dir):
    """Delete files from local storage."""
    for file_name in file_name_list:
        try:
            os.remove(base_dir + "/" + file_name)
        except OSError:
            log.exception('File remove was failed')


@contextmanager
def change_behavior_sys():
    import sys
    import __builtin__

    def exit_dummy(_):
        pass
    tmp_exit = tmp_stderr = tmp_stdout = tmp_raw_input = None
    try:
        with open(settings.GA_OPERATION_STD_ERR, 'w') as err, open(settings.GA_OPERATION_STD_OUT, 'w') as out:
            tmp_exit = sys.exit
            sys.exit = exit_dummy
            tmp_stderr = sys.stderr
            sys.stderr = err
            tmp_stdout = sys.stdout
            sys.stdout = out
            tmp_raw_input = __builtin__.raw_input
            __builtin__.raw_input = get_dummy_raw_input()
            yield
    finally:
        if tmp_exit:
            sys.exit = tmp_exit
        if tmp_stderr:
            sys.stderr = tmp_stderr
        if tmp_stdout:
            sys.stdout = tmp_stdout
        if tmp_raw_input:
            __builtin__.raw_input = tmp_raw_input


def get_dummy_raw_input():
    x = [-1]

    def counter(_):
        x[0] += 1
        return x[0]
    return counter


def get_std_info_from_local_storage():
    with open(settings.GA_OPERATION_STD_ERR, 'r') as err, open(settings.GA_OPERATION_STD_OUT, 'r') as out:
        err_msg, out_msg = err.read(), out.read()
    return err_msg, out_msg


class CSVResponse(HttpResponse):
    """ Return to csv response. """
    def __init__(self, filename, *args, **kwargs):
        super(CSVResponse, self).__init__(content_type='text/csv', *args, **kwargs)
        self['Content-Disposition'] = 'attachment; filename={}'.format(filename)


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return json.JSONEncoder.default(self, o)


class JSONFileResponse(JsonResponse):
    """ Return to json file response. """
    def __init__(self, object=None, filename=None, encoder=JSONEncoder, *args, **kwargs):
        super(JSONFileResponse, self).__init__(object=object, content_type='text/json', encoder=encoder, *args, **kwargs)
        self['Content-Disposition'] = 'attachment; filename={}'.format(filename)

