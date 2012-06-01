import os
import urllib
import requests
import sys
import pymongo
import pprint
import re
import urllib2
import time
import datetime
import traceback
import json
from jinja2 import Template

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0]
sys.path.append( path )

import lib.jira
import lib.crowd
import lib.aws
#import lib.sms
import settings

conn = pymongo.Connection('jira.10gen.cc');
#conn = pymongo.Connection('localhost');
db = conn.jira_alert
last_alert_noncs = db.last_alert_noncs

email_template_str = """
{% for issue in issues %}
    https://jira.mongodb.org/browse/{{issue['key']}} - {{issue['summary']}} 
    Reporter: {{issue['reporter']['fullname']}} from {{issue['reporter']['company']}} ({{issue['reporter']['email']}})
    created on {{issue['created']}}
{% endfor %}
"""

recips = ["support-alerts@10gen.com", "mikeo@10gen.com"]
#recips = ["mikeo@10gen.com"]

email_template = Template(email_template_str)
jira = lib.jira.JiraConnection()

def get_projectrole_byname(name):
    global jira
    for r in jira.getProjectRoles():
        if r.name == name:
            return r
    return None

def chunks(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def send_email(subject, body, who):
    lib.aws.send_email( "info@10gen.com" , subject , body , who)

def generate_email(issues):
    return email_template.render(issues=issues)

def get_issues(limit_time=None):
    customer_role =  get_projectrole_byname("Customer")
    cs_project   =   jira.getProjectByKey("CS")
    cs_people = jira.getProjectRoleActors(customer_role, cs_project)
    cs_names = {}

    for actor in cs_people.roleActors:
        company = actor['descriptor']
        for user in actor['users']:
            cs_names[user['name']] = {"fullname":user['fullname'], "email":user['email'], "name":user['name'], "company":company}


    issues = []

    for chunk in chunks(cs_names.keys(), 200):
        filterrr = 'resolution = Unresolved AND status not in ("Waiting for Customer", "Waiting for bug fix" , "Resolved" ) AND type != Tracking and project != CS'
        filterrr += " AND reporter in (%s)" % (','.join(['"%s"' % n for n in chunk]))
        jql = {"jql": filterrr + " ORDER BY created asc"}
        url_jql = urllib.urlencode(jql)
        url = "https://jira.mongodb.org/rest/api/latest/search?" + url_jql
        x = requests.get(url, auth=("mpobrien", "ek223imi"))
        issues += json.loads(x.content)['issues']

    for issue in issues:
        jirainfo = jira.getIssue(issue['key'])
        if jirainfo:
            issue['reporter']= cs_names[jirainfo['reporter']]
            issue['created'] = jirainfo['created']
            issue['summary'] = jirainfo['summary']

    issues = sorted(issues, key=lambda k: k['created'], reverse=True) 
    if limit_time:
        print "filtering by time"
        issues_out = []
        for issue in issues:
            #print issue['key'], issue['created'], issue['created'] > limit_time, limit_time 
            if issue['created'] > limit_time :
                issues_out.append(issue)

        issues = issues_out
        print "filtered to", len(issues), "new issues"

    return issues


def main():
    issues = get_issues()
    for issue in issues:
        print issue['key'], issue['summary'], issue['created']
    latest_ticket = last_alert_noncs.find_one({"_id":"latest_noncs"})
    if latest_ticket:
        timecheck = latest_ticket['created']
        print "latest time", timecheck
        issues = get_issues(timecheck)
    else:
        issues = get_issues()
    if issues:
        body = generate_email(issues)
        for recip in recips:
            send_email("Issues filed by CS customers in non-CS projects", body, recip)
        newest_issue = issues[0]
        if not latest_ticket or (latest_ticket and newest_issue['created'] > latest_ticket['created']):
            last_alert_noncs.save({"_id":"latest_noncs", "created":newest_issue['created'], "key":newest_issue["key"]})

if __name__ == '__main__': main()
