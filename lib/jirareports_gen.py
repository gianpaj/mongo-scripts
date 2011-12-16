from collections import defaultdict
from math import log
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
import json
import sys
from pymongo import Connection
jirareportsdb = Connection().jira

def get_total_seconds(td):
  return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 1e6) / 1e6

def average_builder(curval, doc):
  if not doc.get('resolutiondate', None):
    return curval
  else:
    return [curval[0] + 1, curval[1] + get_total_seconds((doc['resolutiondate'] - doc['created']))]

def avg_calc(x):
  if x[0] > 0:
    return x[1] / x[0]
  else:
    return 0

def average(values):
  if not values: return None
  return sum(values, 0.0) / len(values)

def log_histogram(data, dockey):
  counts = defaultdict(int)
  minkey = None
  maxkey = None
  for item in data:
    if dockey not in item:
      continue
    origval = item[dockey]
    key = int(log(origval))
    if minkey is None or minkey > key: minkey = key
    if maxkey is None or maxkey < key: maxkey = key
    counts[key] += 1
  if len(counts) > 0:
    for i in xrange(minkey, maxkey):
      if i not in counts:
        counts[i] = 0
  return sorted([(k[0], k[1]) for k in counts.iteritems()], key=lambda t:t[0])

def histogram_by_date(data, factory_init, operation, finalizer):
  counts = defaultdict(factory_init)
  earliest = datetime(year=2990, day=1, month=1)
  latest = datetime(year=1990, day=1, month=1)
  for issue in data:
    if not issue.get('created', None):
      continue
    earliest = min(issue['created'], earliest)
    latest = max(issue['created'], latest)
    key = "%s-%s" % (issue['created'].year, issue['created'].month)
    counts[key] = operation(counts[key], issue)
  if len(counts) > 0:
    curmonth = datetime(year=earliest.year, month=earliest.month, day=1)
    lastmonth = datetime(year=latest.year, month=latest.month, day=1)
    while curmonth <= latest:
      key = "%s-%s" % (curmonth.year, curmonth.month)
      if key not in counts:
        counts[key] = factory_init()
      curmonth += relativedelta(months=1)
    return sorted([(k[0], finalizer(k[1])) for k in counts.iteritems()], key=lambda t:t[0])

def generate_all_engineers():
    periodslist = [p['_id'] for p in jirareportsdb.periods.find()]
    if not periodslist:
      refresh_periods()
      periodslist = [p['_id'] for p in jirareportsdb.periods.find()]
    periodslist.append("all")
    for name in list(jirareportsdb.issues.distinct("assignee")):
        for timeperiod in periodslist:
            print "building report for", name, timeperiod
            report = generate_engineer_report(name, timeperiod)
            report['last_generated'] = datetime.now()
            jirareportsdb.reports.update({"type":"engineer", "name":name,
                                          "period":timeperiod},
                                          report,
                                          upsert=True,
                                          safe=True )

def generate_all_companies():
    companieslist = list(jirareportsdb.companies.find());
    if not companieslist:
        companieslist = list(jirareportsdb.issues.distinct("company"))
        refresh_companies()
        companieslist = jirareportsdb.companies.find();
    periodslist = [p['_id'] for p in jirareportsdb.periods.find()]
    if not periodslist:
        refresh_periods()
        periodslist = [p['_id'] for p in jirareportsdb.periods.find()]
    periodslist.append("all")
    for name in [c['_id'] for c in companieslist]:
        for timeperiod in periodslist:
            print "building report for", name, timeperiod
            report = generate_customer_report(name, timeperiod)
            jirareportsdb.reports.update({"type":"customer",
                                          "name":name,
                                          "period":timeperiod},
                                          report,
                                          upsert=True,
                                          safe=True )


def generate_engineer_report(name, timeperiod="all"):
    time_filter = {}
    if timeperiod is not None and timeperiod != "all":
        year, month = timeperiod.split('-')
        startday = datetime(year=int(year), month=int(month), day=1)
        endday = startday + relativedelta(months=1)
        time_filter['created'] = {"$gte":startday,"$lt":endday}

    issues_query = list(jirareportsdb.issues.find(dict(assignee=name, **time_filter)))
    num_commented = len(issues_query)
    num_resolved = jirareportsdb.issues.find(dict([("assignee",name)], **time_filter)).count()
    resolutions = jirareportsdb.issues.find(dict(assignee=name,resolutiondate={"$exists":True, "$ne":None}, **time_filter),
                                  {"created":1, "resolutiondate":1})

    resolution_times = []
    for i in issues_query:
        if i.get('resolutiondate', None) and i.get('created', None):
            res_time = get_total_seconds(i['resolutiondate'] - i['created'])
            i['resolution_time'] = res_time
            resolution_times.append(res_time)

    first_responses = list(jirareportsdb.issues.find(dict([("comments.0.author",name)], **time_filter)))
    for i in first_responses:
        if i.get('created', None) and i['comments'][0]['created']:
            response_time = get_total_seconds(i['comments'][0]['created'] - i['created'])
            i['response_time'] = response_time

    resolution_time_plot = log_histogram(issues_query, 'resolution_time')
    first_responses_plot = log_histogram(first_responses, 'response_time')

    result = dict(resolution_times=resolution_times,
                avg_resolutiontime = average(resolution_times),
                num_commented=num_commented,
                num_resolved=num_resolved)
    result['resolutions_time_histogram'] = resolution_time_plot
    result['response_time_histogram'] = first_responses_plot

    if resolution_times:
        result['max_resolutiontime'] = max(resolution_times)
        avg_resolution_times = histogram_by_date(issues_query, lambda:[0,0], average_builder, avg_calc)#lambda x: [0,x[1]/x[0]][x[0]>0])
        result['avg_res_times_bymonth'] = avg_resolution_times
    else:
        result['max_resolutiontime'] = None

    if timeperiod == 'all':
        resolutions_by_month = histogram_by_date(issues_query, int, lambda x, y: x+1, lambda y: y)
        if resolutions_by_month:
            result['resolutions_by_month'] = resolutions_by_month

    result['type'] = 'engineer'
    result['name'] = name
    result['period'] = timeperiod
    return result

def generate_customer_report(name, timeperiod='all'):
    time_filter = {}
    if timeperiod is not None and timeperiod != "all":
      year, month = timeperiod.split('-')
      startday = datetime(year=int(year), month=int(month), day=1)
      endday = startday + relativedelta(months=1)
      time_filter['created'] = {"$gte":startday,"$lt":endday}

    issues_query = list(jirareportsdb.issues.find(dict(company=name, **time_filter)))
    num_commented = len(issues_query)
    num_resolved = jirareportsdb.issues.find(dict([("company",name)], **time_filter)).count()
    query = dict([("company",name),("resolutiondate",{"$exists":True, "$ne":None})], **time_filter)
    resolutions = list(jirareportsdb.issues.find(query, {"created":1, "resolutiondate":1}))
    resolution_times = [get_total_seconds(d['resolutiondate'] - d['created']) for d in resolutions if
              (d.get('resolutiondate',None) and d.get('created',None)) ]
    result = dict(resolution_times=resolution_times,
                avg_resolutiontime = average(resolution_times),
                num_commented=num_commented,
                num_resolved=num_resolved)

    if timeperiod == 'all':
      resolutions_by_month = histogram_by_date(issues_query, int, lambda x, y: x+1, lambda y: y)
      if resolutions_by_month:
        result['resolutions_by_month'] = resolutions_by_month

    if resolution_times:
      result['max_resolutiontime'] = max(resolution_times)
      avg_resolution_times = histogram_by_date(issues_query, lambda:[0,0], average_builder, avg_calc)
      result['avg_res_times_bymonth'] = avg_resolution_times
    else:
      result['max_resolutiontime'] = None

    result['type'] = 'customer'
    result['name'] = name
    result['period'] = timeperiod
    return result


def refresh_companies():
  companieslist = list(jirareportsdb.issues.distinct("company"))
  for c in companieslist:
      try:
          jirareportsdb.companies.insert({"_id":c})
      except Exception, e:
          pass

def refresh_periods():
  issues = jirareportsdb.issues.find({},{"created":1})
  periods = set({})
  for issue in issues:
    periodname = "%s-%s" % ( issue["created"].year , issue["created"].month )
    periods.add(periodname)
  for period in periods:
    jirareportsdb.periods.insert({"_id":period})


if __name__ == '__main__':
    generate_all_companies()
    generate_all_engineers()

