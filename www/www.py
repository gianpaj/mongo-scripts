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

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
sys.path.append(here)

# setup web env
env = jinja2.Environment(loader=jinja2.PackageLoader("www", "templates"))
web.config.debug = False
app = web.auto_application()



crowd = Client("http://crowd.10gen.com/crowd/services/SecurityServer?wsdl")


class CorpHome(app.page):
    path="/(?:index.html)?"

    def GET(self):
        web.header('Content-type','text/html')
        return env.get_template("index.html").render()


class MongoFavicon(app.page):
    path="/favicon.ico"

    def GET(self):
        return web.redirect("http://media.mongodb.org/favicon.ico")


class CorpNormal(app.page):
    path = "/(.*)"

    def GET(self,p):
        web.header('Content-type','text/html')
        
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
