"""
CSV utilities
"""
from cStringIO import StringIO

import codecs
import unicodecsv as csv
from django.http import HttpResponse


class TSVWriter(object):
    def __init__(self, f, encoding='utf-16', **kwargs):
        self.queue = StringIO()
        # Not either encoding='utf-16' or encoding='utf-8-sig' works with unicodecsv
        self.writer = csv.writer(self.queue, delimiter='\t', quoting=csv.QUOTE_ALL, **kwargs)
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


def create_tsv_response(filename, header, datarows, encoding):
    """Returns a TSV response for the given header and rows."""
    response = HttpResponse(content_type='text/tab-separated-values')
    response['Content-Disposition'] = 'attachment; filename={0}'.format(filename)
    writer = TSVWriter(response, encoding)
    writer.writerow(header)
    writer.writerows(datarows)
    return response
