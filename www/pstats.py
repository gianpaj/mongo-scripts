from datetime import datetime, date, timedelta
from functools import wraps
from itertools import izip_longest
from corpbase import CorpBase
from pytz import utc
import re
import cStringIO
import csv
import pstatreport
import traceback

import web
app = web.config.app
db = web.config.pstatsdb
env = web.config.env

import json
env.filters['json'] = json.dumps


def pivot(seq, columns):
    """
    >>> pivot(['a', 'b', 'c', 'd', 'e', 'f'], 3)
    ['a', 'c', 'e', 'b', 'd', 'f']
    >>> pivot(['a', 'b', 'c', 'd', 'e', 'f', 'g'], 3)
    ['a', 'd', 'f', 'b', 'e', 'g', 'c']
    >>> pivot(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'], 3)
    ['a', 'd', 'g', 'b', 'e', 'h', 'c', 'f']
    """
    longcols = len(seq) % columns
    height = len(seq) / columns
    cols = []
    i = 0
    for col in xrange(columns):
        num = height
        if col < longcols:
            num += 1
        cols.append(seq[i:i+num])
        i += num

    out = []
    for sub in izip_longest(*cols):
        for thing in sub:
            if thing is not None:
                out.append(thing)

    return out

class Doctest(app.page):
    path = '/doctest'

    def GET(self):
        import doctest
        import inspect
        return doctest.testmod(inspect.getmodule(self.__class__))

def _lock(lockname):
    try:
        db.bookkeeping.find_and_modify(
            {'_id': lockname, 'locked': False},
            {'$set': {'locked': True}},
            upsert=True)
        return True
    except:
        return False

def _unlock(lockname):
    try:
        db.bookkeeping.find_and_modify(
            {'_id': lockname, 'locked': True},
            {'$set': {'locked': False}},
            upsert=True)
        return True
    except:
        return False

def withlock(lockname):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            if _lock(lockname):
                out = func(*args, **kwargs)
                _unlock(lockname)
                return out
            return None
        return inner
    return wrapper

def settimes(lockname):
    def wrapper(func):
        @wraps(func)
        def inner(*args, **kwargs):
            now = datetime.now(utc).replace(tzinfo=None)
            then = datetime(1970, 1, 1)
            record = db.bookkeeping.find_one({'_id': lockname})
            if record and 'lastrun' in record:
                then = record['lastrun']
            kwargs.update(now=now, then=then)
            out = func(*args, **kwargs)
            db.bookkeeping.update({'_id': lockname}, {'$set': {'lastrun': now}})
            return out
        return inner
    return wrapper


class Pstats(CorpBase):
    path = '/pstats'

    @withlock('baseline')
    @settimes('baseline')
    def _update_baseline(self, now, then):
        db.pstats.map_reduce(
            map="""
            function () {
                emit({host:this.host, test:this.test}, {count:1, rps:this.rps, millis:this.mills});
            }
            """,
            reduce="""
                function (key, values) {
                    var out = {count:0, rps:0, millis:0};
                    for (var i in values) {
                        var val = values[i];
                        out.rps = (out.rps * out.count + val.rps * val.count) / (out.count + val.count);
                        out.millis = (out.millis * out.count + val.millis * val.count) / (out.count + val.count);
                        out.count += val.count;
                    }
                    return out;
                }
            """,
            out="baseline",
            reduce_output=True,
            query={'when': {'$gte': then, '$lt': now}, 'info.git': {'$exists': True, '$ne': 'not-scons'}}
        )

    @withlock('distinct')
    @settimes('distinct')
    def _update_distincts(self, now, then):
        db.pstats.map_reduce(
            map="""
                function () {
                    emit({version:this.info.version, bits:this.info.bits || "unknown", os:this.info.os || "unknown"}, 1);
                }
            """,
            reduce="""
                function (key, values) {
                    return 1;
                }
            """,
            out='distinct_info',
            reduce_output=True,
            query={'when': {'$gte': then, '$lt': now}}
        )

        db.pstats.map_reduce(
            map="""
                function() {
                    emit(this.test, 1);
                }
            """,
            reduce="""
                function(key, values) {
                    return 1;
                }
            """,
            out='distinct_test',
            reduce_output=True,
            query={'when': {'$gte': then, '$lt': now}}
        )

    def get_distinct(self, collection):
        return [x['_id'] for x in db[collection].find(fields=['_id'])]

    def GET(self):
        print "hey!!!"
        self._update_baseline()
        self._update_distincts()

        tests = self.get_distinct('distinct_test')
        tests.sort()
        tests = pivot(tests, 3)

        oses = set()
        versions = set()
        bits = set()
        allversions = []
        for record in self.get_distinct('distinct_info'):
            this = {
                'os': record['os'],
                'version': record['version'],
            }
            try:
                this['bits'] = int(record['bits'])
            except:
                this['bits'] = 'unknown'

            oses.add(this['os'])
            versions.add(this['version'])
            bits.add(this['bits'])

            allversions.append(this)

        allversions.sort(key=lambda v: v['os'])
        allversions.sort(key=lambda v: v['bits'])
        allversions.sort(key=lambda v: v['version'], cmp=pstatreport.versioncmp)
        allversions = pivot(allversions, 3)
        allversions = ['%s:%s:%s' % (v['version'].replace('.','_'), v['bits'], v['os']) for v in allversions]

        bits = list(bits)
        versions = list(versions)
        oses = list(oses)
        bits.sort()
        versions.sort(cmp=pstatreport.versioncmp)
        oses.sort()

        web.header('Content-Type', 'text/html')
        return env.get_template('pstats.html').render(
            tests=tests,
            allversions=allversions,
            bits=bits,
            oses=oses,
            versions=versions,
            end=pstatreport.dt('', 'end'),
            start=pstatreport.dt('', 'start'),
        )

class PstatsCSV(app.page):
    path = '/pstats/csv'

    def GET(self):
        params = web.input(versions=[], tests=[])

        for_download = params.pop('dl', '0')
        if for_download.isdigit():
            for_download = bool(int(for_download))
        elif for_download.lower() in ('t', 'f', 'true', 'false', 'y', 'n', 'yes', 'no'):
            for_download = for_download.lower() in ('t', 'true', 'y', 'yes')
        else:
            for_download = bool(for_download)

        baselines = {}
        field = params.get('type')

        for record in db.baseline.find({'_id.test': {'$in': params.get("tests")}}):
            host = record['_id']['host']
            test = record['_id']['test']
            value = record['value'][field]

            if host not in baselines:
                baselines[host] = {}
            baselines[host][test] = float(value)


        try:
          rep = pstatreport.PstatReport(tests=params.get('tests'),
                            hosts=sorted(baselines.keys()),
                            versions=params.get('versions'),
                            startdate=params.get('start'),
                            enddate=params.get('end'),
                            field=field,
                            for_download=False)
          rep.baselines = baselines

        except Exception, e:
          print e
          traceback.print_stack()
          traceback.print_exc()
        except Error, e:
          traceback.print_stack()
          traceback.print_exc()
        y = rep.generate_report()
        try:
          for x in rep.generate_report():
              yield(x)
        except Exception, e:
          print e

        return

