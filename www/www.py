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

from webpy_mongodb_sessions.session import MongoStore
from itertools import ifilter, imap, islice

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.append(here)

import settings

# setup web env
env = jinja2.Environment(loader=jinja2.PackageLoader("www", "templates"))
web.config.debug = False
app = web.auto_application()


#setup crowd
url='file://' + here + '/crowd-fixed.wsdl'
client = Client(url)
auth_context = client.factory.create('ns1:ApplicationAuthenticationContext')
auth_context.name = settings.crowdAppUser
auth_context.credential.credential = settings.crowdAppPassword
appToken = client.service.authenticateApplication(auth_context)


#setup dbs
wwwdb = pymongo.Connection( settings.wwwdb_host ).www
usagedb = pymongo.Connection( settings.usagedb_host ).mongousage
mongowwwdb = pymongo.Connection(settings.mongowwwdb_host).mongodb_www

sessionstore = MongoStore(mongowwwdb, 'sessions')

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

            if client.service.isValidPrincipalToken( appToken , c["auth_token"] , client.factory.create( "ns1:ArrayOfValidationFactor" ) ):
                if isLogout:
                    client.service.invalidatePrincipalToken( appToken , c["auth_token"] )
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
                token = client.service.authenticatePrincipalSimple( appToken , username , password )
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


    def dlDomains(self,pp):
        days = 7
        try:
            days = int(web.input()["days"])
        except:
            pass

        pp["days"] = days
        pp["domains"] = usagedb["gen.domains.day" + str(days)].find().sort('value', pymongo.DESCENDING)

    def newsletterSignups(self, pp):
        sessions = ifilter(lambda session: bool(session.get('email')), imap(
            lambda doc: sessionstore[doc['_id']], mongowwwdb.sessions.find()))
        pp.update(sessions=sessions, ipinfo=mongowwwdb.ipinfo)

    def sessions(self, pp):
        pp.update(
            sessions=[sessionstore[i['_id']] for i in islice(mongowwwdb.sessions.find(), 25)],
            ipinfo=mongowwwdb.ipinfo,
            )

    def dlEvents(self,pp):
        events = list(mongowwwdb.download_events.find())
        sessions = {}
        for e in events:
            sessionid = e['sessionid']
            session = sessionstore[sessionid]
            sessions[sessionid] = session
        pp.update(events=events, sessions=sessions, ipinfo=mongowwwdb.ipinfo)

    def csSignups(self,pp):
        pp["orders"] = wwwdb.orders.find()

    def contributors(self,pp):
        pp["contributors"] = wwwdb.contributors.find()

if __name__ == "__main__":
    app.run()
else:
    application = app.wsgifunc()
