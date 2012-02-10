from pytz import utc
import cStringIO
import re
import csv
from datetime import datetime
import web
import traceback
import sys
from collections import defaultdict
db = web.config.pstatsdb

def calc_average(ss):
    if not ss:
        return 0
    return sum(ss)/len(ss)

def versioncmp(a, b):
    """
    >>> versioncmp('1.9.0-pre-', '1.9.0')
    -1
    >>> versioncmp('1.9.0', '1.9.0')
    0
    >>> versioncmp('1.9.0', '1.9.0-rc0')
    1
    """
    if a == b:
        return 0

    abase, ax = re.match(r'([\d\.]+)(-.*)?', a).groups()
    bbase, bx = re.match(r'([\d\.]+)(-.*)?', b).groups()

    # get rid of Nones
    ax = ax or ''
    bx = bx or ''

    if abase < bbase:
        return -1
    elif abase > bbase:
        return 1

    # else bases are equal
    elif ax == '':
        return 1
    elif bx == '':
        return -1

    elif 'pre' in ax:
        # 'pre' is not in bx, so b is greater
        return -1
    elif 'pre' in bx:
        return 1

    elif 'rc' in ax:
        # 'rc' is not in bx, so a is greater
        return 1
    elif 'rc' in bx:
        return -1

    raise Exception("d'oh")


def dt(date_str, default):
    if date_str:
        year, month, day = map(int, re.match('(\d{4})-(\d{2})-(\d{2})', date_str).groups())
        return datetime(year, month, day)

    dt = datetime.now(utc).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    if default == 'start':
        year = dt.year
        month = dt.month
        month -= 6
        if month < 1:
            year -= 1
            month += 12
        day = dt.day
        while True:
            try:
                dt = dt.replace(year=year, month=month, day=day)
                break
            except:
                day -= 1

    return dt

class PstatReport:
    def __init__(self, tests, hosts, versions, startdate='start', enddate='end', field='rps', for_download=False):
        self.tests = tests
        self.hosts = hosts
        self.field = field
        self.versions = versions
        self.for_download = for_download
        self.startdate = dt(startdate, 'start')
        self.enddate = dt(enddate, 'end')

    def buildversions(self):
        versions_clean = []
        for description in self.versions:
            version, bits, os = description.split(':')
            version = version.replace('_', '.')
            doc = {'info.version': version}
            if os != "unknown":
                doc['info.os'] = os
            if bits != "unknown":
                doc['info.bits'] = int(bits)
            versions_clean.append(doc)
        return versions_clean


    def build_query(self):
        query = {}
        query['info.git'] = {'$exists': True}
        query['test'] = {'$in': self.tests}
        query['gitwhen'] = {'$gte': self.startdate, '$lt': self.enddate}
        #just use all the versions
        #query['$or'] = self.buildversions()
        return query

    def generate_header(self):
        try:
            if self.for_download:
                if len(self.tests) > 1:
                    return 'Date,Git,' + ','.join('%s,N' % test for test in self.tests) + '\n'
                else:
                    return 'Date,Git,' + ','.join(['%s,N' % host for host in self.hosts] + ["AVERAGE,N"]) + '\n'
                    #return 'Date,Git,' + ','.join(['%s,N' % host for host in self.hosts]) + '\n'
            else:
                if len(self.tests) > 1:
                    return 'Date,' + ','.join(self.tests) + '\n'
                else:
                    return 'Date,' + ','.join(self.hosts + ["AVERAGE"]) + '\n'
                    #return 'Date,' + ','.join(self.hosts) + '\n'
        except Exception, e:
            print e


    def generate_report(self):
        header = self.generate_header()
        yield header
        query = self.build_query()
        test_results = db.pstats.find(query).sort([('gitwhen', 1), ('test', 1)])
        lasthash, lastversion = None, None
        row = {}
        loopindex = 0
        for result in test_results:
            hash = result['info']['git']
            gitwhen = result['gitwhen']
            test = result['test']
            version = result['info']['version']
            host = result['host']
            msg = result.get("gitmsg", "no commit msg")

            if lastversion and versioncmp(version, lastversion) < 0:
                # skip rows for versions older
                # than the last we've seen so far
                continue

            if test not in row:
                row[test] = {}
            if host not in row[test]:
                row[test][host] = []
            row[test][host].append(result[self.field])

            if hash != lasthash and lasthash is not None:
                v = ''
                if lastversion is None or versioncmp(version, lastversion) > 0:
                    # version incremented
                    lastversion = version
                    v = version

                if self.for_download:
                    date_field = gitwhen.strftime('%Y/%m/%d %H:%M:%S')
                else:
                    msg = re.sub(r"\W"," ", msg)
                    date_field = '%s|%s|%s|%s|%s' % (
                        gitwhen.strftime('%Y/%m/%d %H:%M:%S'),
                        hash,
                        v,
                        loopindex,
                        msg)
                    #print result.keys()
                    loopindex += 1
                out = [date_field]
                if self.for_download:
                    #out.append(lasthash)
                    out.append(hash)

                if len(self.tests) > 1:
                    for test in self.tests:
                        hostresults = row.get(test, {})
                        if hostresults == {}:
                            out.append('')
                            if self.for_download:
                                out.append('')
                        else:
                            allhosts_avgs = []
                            for host, results in hostresults.iteritems():
                                baseline = self.baselines[host][test]
                                average = float(sum(results)) / len(results)
                                allhosts_avgs.append(average / baseline)
                                #out.append(str(average / baseline))
                                if self.for_download:
                                    out.append(str(len(results)))
                            out.append(str(calc_average(allhosts_avgs)))
                else:
                    # one series per host
                    test = self.tests[0]
                    host_total = 0
                    host_values = []
                    hosts_found = []
                    for host in self.hosts:
                        results = row.get(test, {}).get(host, [])
                        if results:
                            hosts_found.append(host)
                            baseline = self.baselines[host][test]
                            average = float(sum(results)) / len(results)
                            out.append(str(average / baseline))
                            host_values.append(average / baseline)
                            #if self.for_download:
                                #out.append(str(len(results)))
                        else:
                            out.append('')
                            if self.for_download:
                                out.append('')
                    if host_values:
                        out.append(str(float(sum(host_values)) / len(host_values)))
                    else:
                        out.append('')

                    #out.append(str(host_total/len(self.hosts)))


                try:
                  outrowcs = cStringIO.StringIO()
                  cs2 = csv.writer(outrowcs)
                  cs2.writerow([str(x) if x is not None else '' for x in out])
                  yield outrowcs.getvalue()
                except:
                  traceback.print_exc(file=sys.stdout)
                row = {}
            lasthash = hash




