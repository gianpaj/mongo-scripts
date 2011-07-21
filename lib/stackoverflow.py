from datetime import datetime
import urllib
import urllib2
import gzip
import json
import time
import urlparse
import pytz
import time
from cStringIO import StringIO

api_key = '7ZgpArX7yE-fkoERhwPtMQ'

def req(tags, pagesize=100, pagenum=1, sort='activity', fromdate=None, todate=None):
    url = 'http://api.stackoverflow.com/1.1/questions?'
    params = dict(
        tagged=';'.join(tags),
        page=pagenum,
        pagesize=pagesize,
        key=api_key,
        sort=sort,
        body='true',
        answers='true',
    )
    if fromdate:
        if type(fromdate) == datetime:
            tm = fromdate.astimezone(pytz.UTC).timetuple()
            fromdate = time.mktime(tm)
        params['fromdate'] = int(fromdate)
    if todate:
        if type(todate) == datetime:
            tm = todate.astimezone(pytz.UTC).timetuple()
            todate = time.mktime(tm)
        params['todate'] = int(todate)

    url += urllib.urlencode(params)
    response = urllib2.urlopen(url % params)
    body = json.load(gzip.GzipFile(fileobj=StringIO(response.read())))
    return body

def get_questions_and_answers(tags=['mongodb'], fromdate=None, todate=None):
    if type(tags) in (str, unicode):
        tags = [tags]

    pagenum = 1
    questions = []
    question_ids = set()

    while True:
        response = req(tags, pagenum=pagenum, fromdate=fromdate, todate=todate)
        pagenum += 1

        num_added = 0
        for question in response['questions']:
            # skip duplicates
            if question['question_id'] not in question_ids:
                question_ids.add(question['question_id'])
                questions.append(question)
                num_added += 1

        if num_added == 0:
            break

    return questions


if __name__ == '__main__':
    f = datetime(2011, 4, 1, tzinfo=pytz.timezone('America/New_York'))
    print req(['mongodb'], fromdate=f)

