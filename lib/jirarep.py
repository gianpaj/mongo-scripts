import web
from corpbase import CorpBase, authenticated, wwwdb, eng_group, env
from corpbase import jirareportsdb
from collections import defaultdict
from math import log
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from jirareports_gen import generate_engineer_report, generate_customer_report
import json
import sys


class JiraReport(CorpBase):
    def GET(self):
        web.header('Content-type','text/html')
        engineerslist = eng_group
        companieslist = list(jirareportsdb.companies.find());
        if not companieslist:
          companieslist = list(jirareportsdb.issues.distinct("company"))
          refresh_companies()
          companieslist = jirareportsdb.companies.find();

        periodslist = [p['_id'] for p in jirareportsdb.periods.find()]
        if not periodslist:
          refresh_periods()
          periodslist = [p['_id'] for p in jirareportsdb.periods.find()]
        periodslist.sort(reverse=True)

        t = env.get_template("jirareports.html" )
        return t.render(dict(message="hello", engineers=engineerslist, companies=companieslist, periods=periodslist))

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


class JiraEngineerReport(CorpBase):
  def GET(self, name):
    web.header('Content-type','application/json')
    pageparams = web.input()
    timeperiod =  pageparams.get("period", None) or "all"
    info = jirareportsdb.reports.find_one({'period':'all', 'engineer':name})
    time_filter = {}

    report = jirareportsdb.reports.find_one({"type":"engineer", "name":name, "period":timeperiod})
    if (report is None or
        report.get("last_generated", datetime(year=1970,month=1, day=1)) < (datetime.now() -timedelta(days=1))):
        report = generate_engineer_report(name, timeperiod)
        report['last_generated'] = datetime.now()
        jirareportsdb.reports.update({"type":"engineer", "name":name, "period":timeperiod}, report, upsert=True, safe=True )
        del report['last_generated']
        return json.dumps(report)
    else:
        del report['_id']
        del report['last_generated']
        return json.dumps(report)

class JiraCustomerReport(CorpBase):
  def GET(self, name):
    web.header('Content-type','application/json')
    pageparams = web.input()
    timeperiod =  pageparams.get("period", None)
    report = jirareportsdb.reports.find_one({"type":"customer",'period':timeperiod, 'customer':name})
    if report is not None:
        del report['_id']
        return json.dumps(report)
    else:
        report = generate_customer_report(name, timeperiod)
        jirareportsdb.reports.update({"type":"customer", "name":name, "period":timeperiod}, report, upsert=True, safe=True )
        return json.dumps(report)

if __name__ == '__main__':
    generate_all_companies()
    generate_all_engineers()

