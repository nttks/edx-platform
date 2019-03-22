# -*- coding: utf-8 -*-
import unicodecsv as csv
import codecs
from cStringIO import StringIO
from django.utils.translation import ugettext as _
from django.http import HttpResponse
import urllib


def get_utf8_csv(request, filename, delimiter='\t', quotechar="'"):
    tmp_str = request.FILES[filename].file.read()
    tmp_utf8_str = tmp_str.decode('utf-16').replace(quotechar, '')

    result = []
    for line in tmp_utf8_str.splitlines():
        if line.strip():
            result.append(line.split(delimiter))

    return result


class TSVWriter(object):
    def __init__(self, f, encoding='utf-16', delimiter='\t', quoting=csv.QUOTE_ALL, quotechar="'", **kwargs):
        self.queue = StringIO()
        # Not either encoding='utf-16' or encoding='utf-8-sig' works with unicodecsv
        self.writer = csv.writer(self.queue, delimiter=delimiter, quoting=quoting, quotechar=quotechar, **kwargs)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([unicode(s).encode('utf-8') for s in row])
        data = self.queue.getvalue()
        data = data.decode('utf-8')
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def create_tsv_response(filename, header, rows, encoding='utf-16'):
    """
    :param filename: output_file_name
    :param header: csv_header
    :param rows: csv_rows
    :param encoding: default utf-16
    :return: http_output
    """
    response = HttpResponse(content_type='text/tab-separated-values')
    filename = urllib.quote(filename.encode("utf-8"))
    response['Content-Disposition'] = "attachment; filename*=UTF-8''{0}".format(filename)
    writer = TSVWriter(f=response, encoding=encoding)
    writer.writerow(header)
    writer.writerows(rows)
    return response


class CSVWriter(object):
    def __init__(self, f, encoding='cp932', delimiter=',', **kwargs):
        self.queue = StringIO()
        self.writer = csv.writer(self.queue, delimiter=delimiter, escapechar=None, **kwargs)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([unicode(s).encode('cp932') for s in row])
        data = self.queue.getvalue()
        data = data.decode('cp932')
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def create_csv_response(filename, header, rows, encoding='cp932'):
    """
    :param filename: output_file_name
    :param header: csv_header
    :param rows: csv_rows
    :param encoding: default utf-16
    :return: http_output
    """
    response = HttpResponse(content_type='text/csv')
    filename = urllib.quote(filename.encode("utf-8"))
    response['Content-Disposition'] = "attachment; filename*=UTF-8''{0}".format(filename)
    writer = CSVWriter(f=response, encoding=encoding)
    if header is not None:
        writer.writerow(header)
    if rows is not None:
        writer.writerows(rows)
    return response


def get_sjis_csv(request, filename, delimiter=','):
    tmp_str = request.FILES[filename].file.read()
    tmp_sjis_str = tmp_str.decode('cp932')

    result = []
    for line in tmp_sjis_str.splitlines():
        if line:
            line = line.replace('"', '')
        if line.strip():
            result.append(line.split(delimiter))

    return result


class CSVWriterDoubleQuote(object):
    def __init__(self, f, encoding='cp932', delimiter=',', **kwargs):
        self.queue = StringIO()
        self.writer = csv.writer(self.queue, delimiter=delimiter, quoting=csv.QUOTE_ALL, escapechar=None, **kwargs)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([unicode(s).encode('cp932', 'ignore') for s in row])
        data = self.queue.getvalue()
        data = data.decode('cp932')
        data = self.encoder.encode(data)
        self.stream.write(data)
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)


def create_csv_response_double_quote(filename, header, rows, encoding='cp932'):
    """
    :param filename: output_file_name
    :param header: csv_header
    :param rows: csv_rows
    :param encoding: default utf-16
    :return: http_output
    """
    response = HttpResponse(content_type='text/csv')
    filename = urllib.quote(filename.encode("utf-8"))
    response['Content-Disposition'] = "attachment; filename*=UTF-8''{0}".format(filename)
    writer = CSVWriterDoubleQuote(f=response, encoding=encoding)
    writer.writerow(header)
    writer.writerows(rows)
    return response


