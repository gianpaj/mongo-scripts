


import os
import sys
import pymongo
import pprint
import re
import urllib2
import time
import datetime
import traceback

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0] 
sys.path.append( path )

import lib.gmail
import lib.googlegroup
import lib.jira
import lib.crowd
import lib.aws

import settings

# who
#    A - assignee
#    O - owner
#    S - support triage
#    D - dev

# { "jql" : "..." ,           the actual query to run
#   "who" : "AS" ,            list of types
#   "sms" : <Bool>            whether to send an sms for this
#   "digest" : <Bool>         whether or not this should be part of a daily digest. 
#                             if so, goes out at night rather than immediate
#   "freq"   :                # of hours betweeen emails  - None means no cap
#   "filter" :                if True, skip this issue
# }

csBigFilter = """
  project = CS AND 
  resolution = Unresolved AND 
  status not in ("Waiting for Customer", "Waiting for bug fix" , "Resolved" ) AND
  type != Tracking
"""

all10gen = []
def getAll10gen( jira ):
    if len(all10gen) > 0:
        return all10gen

    for g in [ "10gen" , "10gen-eng" , "10gen-support" ]:
        for x in jira.getGroup( g ):
            all10gen.append( x )

    return x

def last_comment_from_10gen( jira , issue ):
    print( issue["key"] )
    comments = jira.getComments( issue["key"] )
    if comments is None or len(comments) == 0:
        return False
    
    c = comments[len(comments)-1]
    who = jira.getUser( c["author"] )
    return who in getAll10gen( jira )

queries = [

    { "name" : "SLA in danger - not assigned" ,
      "who" : "AO" ,
      "digest" : False ,
      "freq" : 2 ,
      "jql" : csBigFilter + " AND assignee is EMPTY and created <= -30m" } ,

    { "name" : "SLA in danger - blocker needs response" ,
      "who" : "AO" ,
      "digest" : False ,
      "freq" : 3 , 
      "filter" : last_comment_from_10gen ,
      "jql" : csBigFilter + " AND priority = blocker AND updated <= -120m" } , 

    { "name" : "SLA in danger - critical needs response" ,
      "who" : "AO" ,
      "digest" : False ,
      "freq" : 6 ,
      "filter" : last_comment_from_10gen ,
      "jql" : csBigFilter + " AND priority = critical AND updated <= -480m" } , 

    { "name": "CS problems not touched in 24 hours" , 
      "jql" : csBigFilter + " AND  updated <= -24h AND issuetype = 'Problem Ticket'" , 
      "who" : "AO" , 
      "sms" : False , 
      "digest" : True  } ,

    { "name": "CS questions not touched in 3 days" , 
      "jql" : csBigFilter + " AND updated <= -72h AND issuetype != 'Problem Ticket'" , 
      "who" : "AO" , 
      "sms" : False , 
      "digest" : True } ,

    { "name" : "Community Private not touched in 3 days" , 
      "jql" : "project = SUPPORT AND status in (Open, \"In Progress\", Reopened) and updated <= -72h" ,
      "who" : "AO" ,
      "sms" : False ,
      "digest" : True } ,

    { "name" : "SERVER - debugging with submitter not touched in a week" , 
      "jql" : "project = SERVER AND fixVersion = 'debugging with submitter' AND ( status = Open or status = Reopened ) and updated <= -7d" ,
      "who" : "A" , 
      "sms" : False , 
      "digest" : True }

#     { "jql" : csBigFilter + " AND updated <= -72h" , 
#       "who" : "A" , 
#       "sms" : False , 
#       "digest" : True } ,

#     { "jql" : "project = SUPPORT AND resolution = Unresolved AND updated <= -48h" , 
#       "who" : "A" , 
#       "sms" : False , 
#       "digest" : True } ,
#     { "jql" : "project = SERVER AND fixVersion = 10165 AND resolution = Unresolved AND updated <= -48h" , 
#       "who" : "A" , 
#       "sms" : False , 
#       "digest" : True } ,
#     { "jql" : csBigFilter + " AND created >= -48h" , 
#       "who" : "S" , 
#       "sms" : True , 
#       "digest" : False }

    ]

inDebug = False


# ---------------
# ---------------
# ---------------

supportTriageList = [] 
def getSupportTriageList():
    global supportTriageList
    
    if len(supportTriageList) == 0:
        supportTriageList += crowd.findGroupByName( "commercial support triage" )
    return supportTriageList

crowd = lib.crowd.Crowd( settings.crowdAppUser , settings.crowdAppPassword )

def expandWho( issue , who ):

    all = []
    for t in who:

        if t == "A":
            n = issue["assignee"]
            if n:
                all.append( n )
                continue
            t = "S"

            
        if t == "S":
            all += getSupportTriageList()
            continue

        if t == "O":
            if "owner" in issue:
                n = issue["owner"]
                if n:
                    all.append(n)
            continue

        raise Exception( "can't handle who type: %s" % t )

    return all

personToEmail = {}
def getEmail( person ):
    if person in personToEmail:
        return personToEmail[person]
    personToEmail[person] = str(crowd.getUser( person )["mail"])
    return str(personToEmail[person])

def debug(msg):
    if True:
        print( msg )

def mail( subject , body , who ):
    if inDebug:
        print( "would send mail [%s] to %s" % ( subject , who ) )
    else:
        lib.aws.send_email( "info@10gen.com" , subject , body , who )


def run( digest ):

    jira = lib.jira.JiraConnection()
    
    conn = pymongo.Connection();
    db = conn.jira_alert
    last_alert = db.last_alert

    messages = {}
    
    for q in queries:

        def inBlackout( issue ):
            if "freq" not in q:
                return False
            
            last = db.last_email.find_one( { "_id" : issue["key"] } )
            
            if last is None:
                if not inDebug:
                    db.last_email.insert( { "_id" : issue["key"] , "last" : datetime.datetime.now() } )
                return False

            diff = datetime.datetime.now() - last["last"]
            diff = (diff.seconds / 3600.0 + diff.days * 24.0 ) 

            if q["freq"] > diff:
                debug( "in blackout key: %s last: %s " % ( issue["key"] , last ) )
                return True

            if not inDebug:
                db.last_email.save( { "_id" : issue["key"] , "last" : datetime.datetime.now() } )
            return False
    

        
        name = q["name"]
        
        if digest != q["digest"]:
            continue

        if "sms" in q and q["sms"]:
            raise Exception( "sms not supported yet" )

        for issue in jira.getIssuesFromJqlSearch( q["jql"] , 1000 ):
            
            if not digest and inBlackout( issue ):
                continue

            if "filter" in q and q["filter"]( jira , issue ):
                debug( "\t\t\t skipping because of filter" )
                continue

            debug( "%s\t%s" % ( issue["key"] , issue["summary"] ) )
            who = q["who"]
            who = set(expandWho( issue , who ))
            debug( "\t" + str(who) )
            
            for w in who:
                if w not in messages:
                    messages[w] = {}
                    
                p = messages[w]
                if name not in p:
                    p[name] = []
                    
                p[name].append( issue )

    return messages

def getCompany(issue):
    if "customFieldValues" not in issue:
        return None

    for x in issue["customFieldValues"]:
        if x["customfieldId"] == "customfield_10030":
            return x["values"][0]
        
    return None
        

def sendEmails( messages , managerSummary , digest ):
    
    mgr = ""

    shortDate = datetime.datetime.now().strftime( "%Y-%b-%m" ) 
    
    for who in messages:
        
        mgr += who + "\n"
        ind = ""

        mymessages = messages[who]
        for name in mymessages:
            mgr += "\t" + name + "\n"
            ind += name + "\n"
            
            for issue in mymessages[name]:
                simple = "http://jira.mongodb.org/browse/%s\t%s\t%s\n" % ( issue["key"] , getCompany(issue) , issue["summary"] )
                mgr += "\t\t" + simple
                ind += "\t" + simple
                
            mgr += "\n"
            ind += "\n"
    
        debug( "will send email to: %s" % who )
        debug( ind )
        if digest:
            subject = "Support Cases open for %s as of %s" % ( who , shortDate )
        else:
            subject = "Jira alerts for %s as of %s" % ( who , shortDate )
        mail( subject , ind , getEmail( who ) )

    if digest:
        subject = "Support Manager Jira Digest %s" % shortDate
    else:
        subject = "Support Manager Jira Alerts %s" % shortDate

    #debug( mgr )
    if managerSummary and len(mgr) > 0:
        for s in getSupportTriageList():
            mgre = getEmail(s)
            debug( "sending to manager: %s " % mgre )
            mail( subject , mgr , mgre )

if __name__ == "__main__":

    digest = False
    
    for x in sys.argv:
        if x == "debug":
            inDebug = True

        if x == "digest":
            digest = True

    try:
        messages = run(digest)
        sendEmails( messages , True , digest )
    except Exception,e:
        print(e)
        traceback.print_exc()
        mail( "jira alert failure" , "%s\n--\n%s" % ( str(e) , traceback.format_exc() ) , "support@10gen.com" )
