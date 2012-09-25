
# system imports
import re
import os
import sys
import pprint
import time

# normal libraries
import web
import pymongo
import gridfs

try:
    import json
except:
    import simplejson as json

# 'corp stuff'
here = os.path.abspath(os.path.dirname(__file__))
sitepkgs = os.path.normpath(os.path.join(here, '../lib/python2.6/site-packages/'))
import site
site.addsitedir(sitepkgs)


import logging

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.append(here)

sys.path.append( here.rpartition( "/" )[0] + "/lib" )
sys.path.append( here.rpartition( "/" )[0] + "/support" )

import settings
import jira

from corpbase import authenticated, CorpBase

import web
scriptMode = False
if __name__ == "__main__":
    scriptMode = True
else:
    app = web.config.app
    env = web.config.env

db = pymongo.Connection()["jira_server_pm"]

issues_collection = db["issues"]
variables_collection = db["variables"]

myjira = jira.JiraRest( username=settings.jira_username, passwd=settings.jira_password, 
                        version="2",
                        cache_collection=db["jira_rest_cache"],
                        cache_time_seconds=7200)

the_custom_fields = None
the_global_versions = None


def getVersions():
    global the_global_versions
    if the_global_versions:
        return the_global_versions
    versions = {}

    for x in myjira.fetch( "project/SERVER/versions" ):
        if x["released"]:
            continue

        name = x["name"]

        ignores = set()
        ignores.add( "random buildbot failures" )
        ignores.add( "debugging with submitter" )

        if name in ignores:
            continue

        if re.match( "\d+\.\d+\.\d+" , name ):
            continue

        score = 0

        if name == "Planning Bucket B":
            score = 10
        elif name == "Planning Bucket A":
            score = 20
        elif name == "minor tech improvements":
            score = 10
        elif name.find( "desired" ) >= 0:
            score = 30
        elif name.find( ".x" ) >= 0:
            score = 50

        x["score"] = score
        versions[name] = x

    the_global_versions = versions
    return versions

def getCustomFields():
    global the_custom_fields
    if the_custom_fields:
        return the_custom_fields
    fixed = {}
    
    fields = myjira.fetch( "field" )
    for field in fields:
        if not field["id"].startswith( "customfield_" ):
            continue
        fixed[field["id"]] = field["name"]
        
    the_custom_fields = fixed
    return fixed

def computeScore( mongoIssue ):
    score = 0
    versions = getVersions()
    for x in mongoIssue["fixVersions"]:
        if x["name"] in versions:
            score = score + versions[x["name"]]["score"]
        
    score = score + mongoIssue["votes"]["votes"]

    if "issuelinks" in mongoIssue and len(mongoIssue["issuelinks"])>0:
        for link in mongoIssue["issuelinks"]:
            key = None
            if "inwardIssue" in link:
                key = link["inwardIssue"]["key"]
            else:
                key = link["outwardIssue"]["key"]
            #pprint.pprint( link )
            if key.startswith( "CS-" ):
                score = score + 70
            elif key.startswith( "SUPPORT-" ):
                score = score + 30
            else:
                score = score + 5
            
    return score

def syncIssues():
    
    start = time.time()
    last_one_query = { "_id" : "last_sync_time" }
    last = db["variables"].find_one( last_one_query )
    if last and ( start - last["time"] ) < 300:
        return

    fields = getCustomFields()
    
    for version_name in getVersions():
        print( version_name )
        issues = myjira.fetch( "search" , 
                               jql='project = server AND resolution is EMPTY AND fixVersion = "%s"' % version_name ,
                               maxResults = 1000 )

        if issues["total"] >= 1000:
            raise Exception( "too many results" )

        for issue in issues["issues"]:
            
            key = issue["key"]
            print( "\t" + key )

            fixed = { "last_sync_time" : start, "key" : key }

            for field in issue["fields"]:
                name = field
                if name.startswith( "customfield_" ):
                    name = fields[name]
                fixed[name] = issue["fields"][field]


            fixed["score"] = computeScore( fixed )
            fixed["last_sync_time"] = start
            fixed["deleted"] = False

            issues_collection.update( { "_id" : key } , { "$set" : fixed } , upsert=True )


    issues_collection.update( { "last_sync_time" : { "$lt" : start } } , { "$set" : { "deleted" : True } } , multi=True )
    
    db["variables"].update( { "_id" : "last_sync_time" } , { "$set" : { "time" : start } } , upsert = True )


def query( fixVersion = None , limit = 10 ):
    q = { "deleted" : False }
    if fixVersion:
        q["fixVersions.name"] = fixVersion
    return issues_collection.find( q ).sort( "score", pymongo.DESCENDING).limit( limit )

def scoredKeys( fixVersion = None ):
    query = { "deleted" : False }
    if fixVersion:
        query["fixVersions.name"] = fixVersion
    result = issues_collection.map_reduce( """
function(){ 
    var score = this.score; 
    if ( this.mongoDollars ) { 
        for ( x in this.mongoDollars ){ 
               score += this.mongoDollars[x]; 
        } 
     } 
     emit( this._id , score ); 
}
""" ,
"""
function(k,vs) { 
     return Array.sum(vs); 
}""" , { "inline" :True } , query=query)

    result = [ ( x["_id"] , x["value"] ) for x in result["results"] ]
    result.sort( lambda x,y: int(y[1] - x[1]) )

    return result


mongoDollarsPrefix = "mongoDollars"
mongoDollarsMax = 1000

def getDonatedSoFar( username ):
    result = db.command( "aggregate" , "issues" , 
                         pipeline=[ { "$match" : { "deleted" : False } } , 
                                    { "$group" : { "_id" : 1 , "total" : { "$sum" : "$%s.%s" % ( mongoDollarsPrefix , username ) } } } ] )
    return result["result"][0]["total"]
    
if not scriptMode:
    class ListView(app.page, CorpBase):

        @authenticated
        def GET(self, pageParams):
            params = dict(web.input())
            syncIssues()
            
            username = pageParams["user"]
            username = username.replace( "." , "_" )
            donatedSoFar = getDonatedSoFar( username )
            
            msg = None
            search = ""
            
            if "key" in params and "md" in params:
                wantToDonate = int(params["md"])
                if ( wantToDonate + donatedSoFar ) > mongoDollarsMax:
                    msg = "trying to cheat, eh? (you're donating more than you are allowed)"
                else:
                    issues_collection.update( { "_id" : params["key"] } , 
                                              { "$set" : { "%s.%s" % ( mongoDollarsPrefix , username ) : wantToDonate } } )
                    donatedSoFar = getDonatedSoFar( username )
                    msg = "you donated %s to %s" % ( wantToDonate , params["key"] )

            
            queryFixVersion = None

            if "fixVersion" in params:
                queryFixVersion = params["fixVersion"]

            
            def fixMongoIssue(issue):
                totalScore = issue["score"]
                issue["myDonation"] = 0


                if mongoDollarsPrefix in issue:
                    x = issue[mongoDollarsPrefix]
                    if username in x:
                        issue["myDonation"] = x[username]
                    
                    for u in x:
                        totalScore = totalScore + x[u]
                        
                issue["totalScore"] = totalScore
                return issue

            issues = []
            if "search" in params:
                search = params["search"]
                jql='project = server AND resolution is EMPTY AND summary ~ "%s" ' % search
                for x in myjira.fetch( "search" , jql=jql, maxResults=100 )["issues"]:
                    mi = issues_collection.find_one( { "_id" : x["key"] } )
                    if not mi:
                        msg = "can't find message for %s" % x["key"]
                    else:
                        issues.append( fixMongoIssue( mi ) )
            elif "mine" in params and params["mine"]:
                for i in issues_collection.find( { "mongoDollars." + username : { "$gt" : 0 } } ):
                    issues.append( fixMongoIssue( i ) )
            else:
                for k,s in scoredKeys(queryFixVersion):
                    issues.append( fixMongoIssue( issues_collection.find_one( { "_id" : k } ) ) )

            return env.get_template( "pm/list.html" ).render( issues=issues,
                                                              versions=getVersions(),
                                                              search=search,
                                                              msg=msg,
                                                              donatedSoFar=donatedSoFar,
                                                              donateLeft=mongoDollarsMax-donatedSoFar,
                                                              queryFixVersion=queryFixVersion,
                                                              user=pageParams["user"])
        

if __name__ == "__main__":
    command = "sync"
    if len(sys.argv) > 1:
        command = sys.argv[1]

    if command == "sync":
        syncIssues()
    elif command == "query":
        for x in query():
            print( "%s\t%d" % ( x["key"], x["score"] ) )
    elif command == "scored":
        fixVersion = None
        if len(sys.argv)>2:
            fixVersion = sys.argv[2]
        for x in scoredKeys(fixVersion)[0:10]:
            print( x )
    elif command == "search":
        jql='project = server AND resolution is EMPTY AND summary ~ "%s" ' % sys.argv[2]
        issues = myjira.fetch( "search" , jql=jql, maxResults=100 )
        for x in issues["issues"]:
            print( x["key"] )
