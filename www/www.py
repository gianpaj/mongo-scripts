from __future__ import with_statement

import re
import os
import sys

import subprocess

import httplib
import urllib2

import jinja2
import web

from pymongo import Connection
from suds.client import Client

import settings

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
sys.path.append(here)

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



class CorpFavicon(app.page):
    path="/favicon.ico"

    def GET(self):
        return web.redirect("http://media.mongodb.org/favicon.ico")


class CorpNormal(app.page):
    path = "/(.*)"

    def checkAuth(self):
        res = { "ok" : False }

        c = web.webapi.cookies()

        if "auth_user" not in c:
            return res
        if "auth_token" not in c:
            return res
        
        res["user"] = c["auth_user"]

        if client.service.isValidPrincipalToken( appToken , c["auth_token"] , client.factory.create( "ns1:ArrayOfValidationFactor" ) ):
            res["ok"] = True
            return res
        
        return False

    def POST(self,p):
        blah

    def GET(self,p):
        
        authResult = self.checkAuth()
        if not authResult["ok"]:
            return env.get_template( "login.html" , authResult ).render( authResult )

        web.header('Content-type','text/html')
        
        web.webapi.setcookie( "a" , "b" )
        print( web.webapi.cookies() )

        if p == "":
            p = "index.html"
        
        if not p.endswith( ".html" ):
            p = p + ".html"

        t = env.get_template( p )
        return t.render(path=p)


if __name__ == "__main__":
    app.run()
else:
    application = app.wsgifunc()
