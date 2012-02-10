from datetime import datetime, timedelta
import json
from pytz import utc
import time
import urllib2

from pymongo.errors import DuplicateKeyError
import pymongo
import sys
from os.path import abspath, dirname, join
sys.path.insert(0, abspath(join(dirname(__file__), '..', 'www')))

import settings
db = pymongo.Connection(settings.pstats_host).perf
db.authenticate(settings.pstats_username, settings.pstats_password)

def str_to_date(datestr):
    offset = timedelta()
    if datestr[-6] == '-' and datestr[-3] == ':':
        hours, minutes = int(datestr[-6:-3]), int(datestr[-2:])
        offset = timedelta(hours=hours, minutes=minutes)

    out = datetime.strptime(datestr[:-6], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=utc)
    out += offset
    return out.replace(tzinfo=None)

def get_json(page=1):
    url = 'http://github.com/api/v2/json/commits/list/mongodb/mongo/master'

    if page != 1:
        url += '?page=%d' % page

    out = urllib2.urlopen(url)
    return json.load(out)['commits']

def yield_commits():
    # yield commits one at a time, forever;
    # convert date strings to datetimes
    page = 1
    while True:
        for commit in get_json(page):
            # 'authored_date': u'2011-08-29T11:13:21-07:00',
            # 'committed_date': u'2011-08-29T12:36:41-07:00',
            commit['authored_date'] = str_to_date(commit['authored_date'])
            commit['committed_date'] = str_to_date(commit['committed_date'])
            yield commit
        page += 1

        # we're allowed 60 req/min
        time.sleep(1)

def yield_commits_since(since_date):
    for commit in yield_commits():
        if commit['committed_date'] < since_date:
            break
        yield commit

def sync_commits():
    if db.commits.count():
        last = db.commits.find().sort('when', -1).limit(1).next()['when']
    else:
        last = db.pstats.find().sort('when', 1).limit(1).next()['when']

    for commit in yield_commits_since(last):
        try:
            print db.commits.save({
                '_id': commit['id'],
                'when': commit['committed_date'],
                'author': commit['author'],
                'url': 'https://github.com' + commit['url'],
                'message': commit['message'],
            }, safe=True)
        except DuplicateKeyError:
            pass

def annotate_pstats():
    commits_by_id = dict((c['_id'], {"when":c['when'], "msg":c['message']}) for c in db.commits.find())
    print commits_by_id.keys()
    #query = {'gitwhen': {'$exists': False}, 'info.git': {'$exists': True}}
    query = {'info.git': {'$exists': True}, 'gitwhen': {'$exists': False}}
    for test in db.pstats.find(query, snapshot=True):
        hash = test['info']['git']
        if hash in commits_by_id:
            commit = commits_by_id[hash]
            if 'msg' not in commit:
              pass #"no message!"
            db.pstats.update({'_id': test['_id']},
                  {'$set': {'gitwhen': commit['when'], "gitmsg":commit['msg']}}, safe=True)
            print "updated", test['_id']



if __name__ == '__main__':
    sync_commits()
    annotate_pstats()

