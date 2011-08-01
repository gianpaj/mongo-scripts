from __future__ import with_statement

import re
import os
import sys

import subprocess

import httplib
import urllib2

import jinja2
import web

import pymongo
from suds.client import Client

from itertools import ifilter, imap, islice

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.append(here)

sys.path.append( here.rpartition( "/" )[0] + "/lib" )
sys.path.append( here.rpartition( "/" )[0] + "/support" )

import settings
import crowd
import google_group_to_jira
import jira

# setup web env
env = jinja2.Environment(loader=jinja2.PackageLoader("www", "templates"))
web.config.debug = False
app = web.auto_application()


#setup crowd
crowd = crowd.Crowd( settings.crowdAppUser , settings.crowdAppPassword )

#setup dbs
wwwdb = pymongo.Connection( settings.wwwdb_host ).www
usagedb = pymongo.Connection( settings.usagedb_host ).mongousage
mongowwwdb = pymongo.Connection(settings.mongowwwdb_host).mongodb_www

myggs = google_group_to_jira.ggs("jira.10gen.cc",False)
myjira = jira.JiraConnection()

class CorpFavicon(app.page):
    path="/favicon.ico"

    def GET(self):
        return web.redirect("http://media.mongodb.org/favicon.ico")


class CorpNormal(app.page):
    path = "/(.*)"

    def checkAuth(self,isLogout):
        res = { "ok" : False }

        c = web.webapi.cookies()
        if "auth_user" in c and "auth_token" in c:
            res["user"] = c["auth_user"]

            if crowd.isValidPrincipalToken( c["auth_token"] ):
                if isLogout:
                    crowd.invalidatePrincipalToken( c["auth_token"] )
                else:
                    res["ok"] = True
                return res
        
        params = web.input()
        if "user" in params and "pwd" in params:
            username = params["user"]
            password = params["pwd"]

            if username is None or password is None:
                return res
            
            try:
                token = crowd.authenticatePrincipalSimple( username , password )
            except Exception,e:
                res["err"] = str(e)
                return res;

            if not token:
                res["err"] = "bad username/password"
                return res
            
            web.webapi.setcookie( "auth_user" , username )
            web.webapi.setcookie( "auth_token" , token )
            res["ok"] = True
            return res
        
        return res

    def POST(self,p):
        return self.GET(p)

    def GET(self,p):
        web.header('Content-type','text/html')
        
        pageParams = self.checkAuth( p=="logout")
        if not pageParams["ok"]:
            return env.get_template( "login.html" , pageParams ).render( pageParams )

        if p == "logout":
            return web.redirect( "/" )
        
        if p in dir(self):
            getattr(self,p)(pageParams)

        #print( pageParams )
            
        #fix path
        if p == "":
            p = "index.html"
        
        if not p.endswith( ".html" ):
            p = p + ".html"
    
        pageParams["path"] = p

        t = env.get_template( p )
        return t.render(**pageParams)


    def gggiframe(self,pp):
        subject = web.input()["subject"]
        simple = myggs.simple_topic( subject )
        
        topics = []
        for x in myggs.topics.find( { "subject_simple" : simple } ):
            if "jira" in x:
                key = x["jira"]
                issue = myjira.getIssue( key )
                x["assignee"] = issue["assignee"]
            else:
                x["assignee"] = None
                x["jira"] = None
            topics.append( x )

        pp["topics"] = topics

        


    def dlDomains(self,pp):
        days = 7
        try:
            days = int(web.input()["days"])
        except:
            pass

        pp["days"] = days
        pp["domains"] = usagedb["gen.domains.day" + str(days)].find().sort('value', pymongo.DESCENDING)

    def newsletterSignups(self, pp):
        pp.update(
            newsletter_signups=mongowwwdb.newsletter_signups.find(
                sort=[('time', pymongo.DESCENDING)]),
            sessions=mongowwwdb.sessions,
            ipinfo=mongowwwdb.ipinfo,
            nsignups=mongowwwdb.newsletter_signups.count(),
            )

    def dlEvents(self, pp, limit=100):
        input = web.input()
        try:
            skip = int(input.get('skip', 0))
        except:
            skip = 0
        nextskip = prevskip = None
        ndownloads = mongowwwdb.download_events.count()
        if skip + limit < ndownloads:
            prevskip = skip + limit
        if skip - limit >= 0:
            nextskip = skip - limit
        pp.update(
            download_events=mongowwwdb.download_events.find(
                sort=[('time', pymongo.DESCENDING)]).skip(skip).limit(limit),
            sessions=mongowwwdb.sessions,
            ipinfo=mongowwwdb.ipinfo,
            limit=limit,
            prevskip=prevskip,
            skip=skip,
            nextskip=nextskip,
            ndownloads=ndownloads,
            )

    def csSignups(self,pp):
        pp["orders"] = wwwdb.orders.find()

    def contributors(self,pp):
        pp["contributors"] = wwwdb.contributors.find()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        app.run()
    else:
        cmd = sys.argv[1]
        if cmd == "crowdtest":
            x = crowd.findGroupByName( "10gen-eng" )
            for z in x:
                print(z)
                print( "\t" + str( crowd.getUser( z ) ) )
        else:
            print( "unknown www command: " + cmd )
else:
    application = app.wsgifunc()
