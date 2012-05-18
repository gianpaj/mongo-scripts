import jinja2
import os
import pymongo
import web

import settings

#setup dbs
jirareportsdb = pymongo.Connection( settings.jirareports_host ).jira
wwwdb = pymongo.ReplicaSetConnection(settings.wwwdb_host, replicaset="www-c").www
usagedb = pymongo.Connection( settings.usagedb_host ).mongousage
mongowwwdb = pymongo.Connection(settings.mongowwwdb_host).mongodb_www
corpdb = pymongo.Connection(settings.corpdb_host).corp
pstatsdb = pymongo.Connection(settings.pstats_host).perf
pstatsdb.authenticate(settings.pstats_username, settings.pstats_password)
ftsdb =  pymongo.connection.Connection(settings.fts_host, slave_okay=True).www
#setup crowd
import crowd
the_crowd = crowd.Crowd( settings.crowdAppUser , settings.crowdAppPassword )
eng_group = the_crowd.findGroupByName( "10gen-eng" )

here = os.path.dirname(os.path.abspath(__file__))
env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(here, '../www/templates')))

class CorpBase:
    def checkAuth(self,isLogout):
        res = { "ok" : False }

        c = web.webapi.cookies()
        if "auth_user" in c and "auth_token" in c:
            res["user"] = c["auth_user"]
            res["users"] = [str(u) for u in eng_group]

            if the_crowd.isValidPrincipalToken( c["auth_token"] ):
                if isLogout:
                    the_crowd.invalidatePrincipalToken( c["auth_token"] )
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
                token = the_crowd.authenticatePrincipalSimple( username , password )
            except Exception,e:
                res["err"] = str(e)
                return res

            if not token:
                res["err"] = "bad username/password"
                return res

            web.webapi.setcookie( "auth_user" , username )
            web.webapi.setcookie( "auth_token" , token )
            res["ok"] = True
            return res

        return res

from functools import wraps

# decorator
def authenticated(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        web.header('Content-type','text/html')

        pageParams = self.checkAuth(isLogout=(len(args) and args[0]=="logout"))
        if not pageParams["ok"]:
            return env.get_template( "login.html" , pageParams ).render( pageParams )

        #        print path, pageParams, args, kwargs
        return f(self, pageParams, *args, **kwargs)
    return wrapper
