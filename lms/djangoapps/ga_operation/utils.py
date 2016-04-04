# -*- coding: utf-8 -*-
import os

from django.conf import settings

from boto.s3.connection import S3Connection
from boto.exception import S3ResponseError
from boto.s3.key import Key


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


def delete_files(file_name_list):
    """Delete files from local storage."""
    for file_name in file_name_list:
        os.remove(settings.PDFGEN_BASE_PDF_DIR + "/" + file_name)

