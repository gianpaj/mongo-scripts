import os
import sys
import settings
import suds.sudsobject
import datetime
from pymongo import Connection
from pymongo.errors import DuplicateKeyError
import types
import pytz
from pytz import timezone

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0]
sys.path.append( path )
import lib.jira
import lib.crowd
import lib.aws
import argparse
from jinja2 import Template

import pprint
pp = pprint.PrettyPrinter(depth=16)
VERBOSE = False

jira = lib.jira.JiraConnection()

db = Connection().jira2

report_template = Template(
"""
    Support Stats for the week of {{week_start}} to {{week_finish}}

    Issues Opened / Closed 
    This week: {{opened_issues|count}} / {{closed_issues|count}}
    Last week: {{opened_1wago|count}} / {{closed_1wago|count}}
    2 weeks ago: {{opened_2wago|count}} / {{closed_2wago|count}}

    Number of Issues Filed by Distinct Customers ({{issues_by_customer|count}}):
        {% for info in issues_by_customer %} {{info['_id']}} : {{info['total']}}
        {% endfor %}
""")

def fix_custom_fields(issue):#{{{
    for cs in issue["customFieldValues"]:
        name = db.customfields.find_one({ "_id" : cs.customfieldId})
        issue[name["name"]] = cs.values
    del issue.customFieldValues
    return issue#}}}

def pythonify_suds_obj(obj):#{{{
   # recursively call suds.sudsobject.asdict()
   # on the passed-in object and its attributes
   if type(obj) != types.InstanceType:
       return obj

   objdict = suds.sudsobject.asdict(obj)
   for key, value in objdict.items():
       if type(value) == types.ListType:
           objdict[key] = [pythonify_suds_obj(elem) for elem in value]
       elif type(value) == types.InstanceType:
           objdict[key] = pythonify_suds_obj(value)
   return objdict#}}}

def update_custom_fields():#{{{
    for field in jira.getCustomFields():
        field["_id"] = field["id"]
        db.customfields.save(pythonify_suds_obj(field))
#}}}

def populate_project(project='CS', extra_filter=None):
    update_custom_fields()
    for issue in get_all_issues(project, extra_filter):
        fix_custom_fields(issue)
        print "storing issue", issue['key']
        issue['_id'] = issue['key']
        try:
            issue["comments"] = jira.getComments( issue["key"] )
        except:
            print "got an error"
        issue["resolutiondate"] = jira.getResolutionDateByKey(issue["key"])
        issue = pythonify_suds_obj(issue)
        db.issues.save(issue, safe=True)
        print "stored issue", issue['key']

def main():
    parser = argparse.ArgumentParser(description="Script for populating mongodb mirror of JIRA and generating reports")
    parser.add_argument("--project", dest="project", default=None, help="Project name (CS, FREE, etc)")
    parser.add_argument("--report", action="store_true", dest="report", help="Generate a report")
    parser.add_argument("--load", action="store_true", dest="load", help="Load an entire project")
    parser.add_argument("--loadrecent", action="store_true", dest="loadrecent", help="Refresh recent issues in project")
    parser.add_argument("--verbose", action="store_true", dest="verbose", help="Refresh recent issues in project")
    global VERBOSE

    results = parser.parse_args()
    if results.verbose:
        VERBOSE = True
    if not results.project:
        print "Project parameter --project needed"
        sys.exit(1)

    if results.loadrecent:
        print "Refreshing recent issues in project: ", results.project
        extra_filter = '(updated > "-4w 2d" or created > "-4w 2d" ) AND '
        populate_project(results.project, extra_filter)
    elif results.load:
        print "Refreshing entire project: ", results.project
        populate_project(results.project)

    if results.report:
        eastern = timezone('US/Eastern')
        today_noon = eastern.localize(datetime.datetime.today().replace(hour=12, minute=0, second=0, microsecond=0))
        today_noon_utc = today_noon.astimezone(pytz.utc)
        weekago_noon_utc = today_noon_utc - datetime.timedelta(days=7);

        for project in ('CS', 'FREE'):
            wn = WeeklyNewsletter(project=project, week_start=weekago_noon_utc, week_finish=today_noon_utc)
            openkeys = set([x['_id'] for x in wn.issues_opened()])
            closedkeys = set([x['_id'] for x in wn.issues_closed()])
            openkeys_1wago = set([x['_id'] for x in wn.issues_opened(days_offset=7)])
            closedkeys_1wago = set([x['_id'] for x in wn.issues_closed(days_offset=7)])
            openkeys_2wago = set([x['_id'] for x in wn.issues_opened(days_offset=14)])
            closedkeys_2wago = set([x['_id'] for x in wn.issues_closed(days_offset=14)])
            issues_by_customer = wn.issues_by_customer()
            reportdoc = {"_id":project + "-" + str(weekago_noon_utc) + "," + str(today_noon_utc)}
            reportdoc['project'] = project 
            reportdoc['openkeys'] = list(openkeys) 
            reportdoc['closedkeys'] = list(closedkeys) 
            reportdoc['openkeys_1wago'] = list(openkeys_1wago) 
            reportdoc['closedkeys_1wago'] = list(closedkeys_1wago) 
            reportdoc['openkeys_2wago'] = list(openkeys_2wago) 
            reportdoc['closedkeys_2wago'] = list(closedkeys_2wago) 
            db.reports.save(reportdoc)

            print "Project: ", project
            print report_template.render({
                                    "week_start" : wn.week_start, 
                                    "week_finish" : wn.week_finish,
                                    "opened_issues": openkeys,
                                    "closed_issues": closedkeys,
                                    "opened_1wago" : openkeys_1wago,
                                    "closed_1wago" : closedkeys_1wago,
                                    "opened_2wago" : openkeys_2wago,
                                    "closed_2wago" : closedkeys_2wago,
                                    "issues_by_customer" : issues_by_customer})

class Report(object):
    pass

class WeeklyNewsletter(Report):

    def __init__(self, project='CS', week_start=None, week_finish=None, recent=True): 
        self.project=project
        if not week_start or not week_finish:
            self.week_finish = datetime.datetime.utcnow()
            self.week_start = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        else:
            self.week_finish = week_finish
            self.week_start = week_start
        self.recent = recent

    def run_aggr(self, pipeline):
        cmd = {"aggregate":"issues", "pipeline":[]}
        filters = {"$match":{"project":self.project}}
        cmd['pipeline'].append(filters)
        if self.recent:
            month_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)
            cmd['pipeline'].append( {"$match":{"$or":[{"created":{"$gte":month_ago}}, 
                                                      {"updated":{"$gte":month_ago}}]}})

        cmd['pipeline'] += pipeline
        if VERBOSE:
            print pipeline
        return db.command(cmd)

    def issues_opened(self, days_offset=None):
        lowerbound, upperbound = self.week_start, self.week_finish
        if days_offset:
            lowerbound -= datetime.timedelta(days=days_offset) 
            upperbound -= datetime.timedelta(days=days_offset) 
        cmdresult = self.run_aggr([ 
            {"$match": {"created":{"$gt": lowerbound, "$lt": upperbound}}},
            {"$project":{"_id":1}} ])
        return cmdresult['result']

    def issues_by_customer(self, days_offset=None):
        lowerbound, upperbound = self.week_start, self.week_finish
        if days_offset:
            lowerbound -= datetime.timedelta(days=days_offset) 
            upperbound -= datetime.timedelta(days=days_offset) 
        cmdresult = self.run_aggr([ 
            {"$unwind": "$company"},
            {"$match": {"created":{"$gt": lowerbound, "$lt": upperbound}}},
            {"$group": {"_id":"$company", "total": {"$sum":1}} },
            {"$sort": {"total":-1} }
            ])

        return cmdresult['result']

    def issues_closed(self, days_offset=None):
        lowerbound, upperbound = self.week_start, self.week_finish
        if days_offset:
            lowerbound -= datetime.timedelta(days=days_offset) 
            upperbound -= datetime.timedelta(days=days_offset) 
        cmdresult = self.run_aggr([ 
            {"$match": {"resolutiondate":{"$gt": lowerbound, "$lt": upperbound}}},
            {"$project":{"_id":1}} ])
        return cmdresult['result']

def get_all_issues(project='CS', extra_filter=None):#{{{
    num_found = 1
    last_key = None
    while num_found > 0:
        query = "project = %s and type != tracking" % project
        if last_key: 
            query += " and key > %s" % last_key
        query += " order by key asc"

        if extra_filter: 
            query = extra_filter + " " + query

        num_found = 0
        for issue in jira.getIssuesFromJqlSearch(query, 100):
            last_key = issue['key']
            num_found += 1
            yield issue#}}}

if __name__ == '__main__': main()
