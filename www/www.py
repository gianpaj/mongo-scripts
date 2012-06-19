import logging
import os
import sys
import pprint


try:
    import json
except:
    import simplejson as json

import web
import pymongo
import gridfs
import bson

web.config.debug = False

# some path stuff
here = os.path.dirname(os.path.abspath(__file__))
if here not in sys.path:
    sys.path.append(here)

sys.path.append( here.rpartition( "/" )[0] + "/lib" )
sys.path.append( here.rpartition( "/" )[0] + "/support" )


from corpbase import env, CorpBase, authenticated, the_crowd, eng_group, wwwdb, mongowwwdb, usagedb, pstatsdb, corpdb, ftsdb

from codeReview import CodeReviewAssignmentRules, CodeReviewAssignmentRule, CodeReviewCommit,\
    CodeReviewCommits, CodeReviewPostReceiveHook, CodeReviewPatternTest

import google_group_to_jira
import jira
from jirarep import JiraReport, JiraEngineerReport, JiraCustomerReport
import jinja2



from util import _url_split, url_cmp





class auto_application(web.auto_application):
    # overrides application.add_mapping to
    # ensure that URLs are considered in an
    # order that puts more specific URLs first

    # URLs here (include leading slash) are not
    # logged as 404s in the notfound() method

    ignored_404s = set([
        '/favicon.ico',
        '/robots.txt',
    ])

    def __init__(self, *args, **kwargs):
        web.auto_application.__init__(self, *args, **kwargs)
        self._link_map = {}

    def add_mapping(self, path, cls):
        # sort mappings by specificity, with
        # most-specific first
        web.auto_application.add_mapping(self, path, cls)
        if web.__version__ == '0.36':
            # in .36 self.mapping is a sequence of 2-tuples
            self.mapping.sort(cmp=url_cmp, key=lambda pair: pair[0])
        elif web.__version__ == '0.34':
            # in .34 self.mapping is
            # a sequence of [url, cls, url, cls, ...]
            # rather than a sequence of 2-tuples
            pairs = [(self.mapping[i], self.mapping[i+1]) for i in range(0, len(self.mapping), 2)]
            pairs.sort(cmp=url_cmp, key=lambda pair: pair[0])
            mapping = []
            for pair in pairs:
                mapping.extend(pair)
            self.mapping = tuple(mapping)

        # also set a dictionary of controller class
        # name (lowercased) to split url, to accelerate
        # the link() function
        self._link_map[cls.__name__.lower()] = tuple(_url_split(path or cls.path))




# setup web env
env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(here, "templates")))
web.config.debug = False
app = auto_application()
web.config.app = app


# share some globals through web.config

web.config.env = env
web.config.wwwdb = wwwdb
web.config.usagedb = usagedb
web.config.mongowwwdb = mongowwwdb
web.config.pstatsdb = pstatsdb
web.config.ftsdb = ftsdb
from perfstats import Pstats, PstatsCSV

# import other handlers
import perfstats
import clienthub



myggs = google_group_to_jira.ggs("stats.10gen.cc",False)
myjira = jira.JiraConnection()

class JiraMulti(CorpBase):

    @authenticated
    def GET(self,pageParams):
        web.header('Content-type','text/json')
        res = self.getIssues( web.input()["issues"].split( "," ) )
        return json.dumps( res , sort_keys=True, indent=4 )


    def getIssues(self,keyList):
        res = {}
        for key in keyList:
            key = key.strip()
            if len(key) > 0:
                res[key] = self.getIssueDICT(key)
        return res

    def getIssueDICT(self,key):

        small = {}

        try:
            issue = myjira.getIssue( key )
            #pprint.pprint( issue )

            small["assignee"] = issue["assignee"]
            small["status"] = issue["status"]
            small["fixVersions"] = [ x["name"] for x in issue["fixVersions"] ]
            small["priority"] = issue["priority"]

            for x in issue["customFieldValues"]:
                if  x["customfieldId"] == "customfield_10030":
                    small["customer"] = x["values"]

        except Exception,e:
            small["error"] = str(e)

        return small

class CorpFavicon:
    def GET(self):
        return web.redirect("http://media.mongodb.org/favicon.ico")

class CorpNormal(CorpBase):
    @authenticated
    def POST(self, pageParams, p=''):
        return self.GET(p)

    @authenticated
    def GET(self, pageParams, p=''):
        if p == "logout":
            return web.redirect( "/" )

        if p == "gridfsimg":
            gfs = gridfs.GridFS( corpdb )
            f = gfs.get( bson.ObjectId( web.input()["id"] ) )
            if not f:
                return
            web.header('Content-type','image/jpeg')
            return f.read()

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
        pp["simple"] = simple

        topics = []
        for x in myggs.topics.find( { "subject_simple" : simple } ):
            if "jira" in x:
                key = x["jira"]
                try:
                    issue = myjira.getIssue( key )
                except:
                    myjira = jira.JiraConnection()
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


    def phonebook(self,pp):
        pp["people"] = corpdb.phonebook.find()

    def person(self,pp):
        inp = web.input()

        person = corpdb.phonebook.find_one( { "_id" : inp["id"] } )

        if "deletephoto" in inp:
            gfs = gridfs.GridFS( corpdb )
            gfs.delete( bson.ObjectId( web.input()["deletephoto"] ) )

        pp["images"] = corpdb.fs.files.find( { "user" : inp["id"] } )

        # --- edit ----
        if "edit" in inp and "true" == inp["edit"]:
            pp["edit"] = True
        else:
            pp["edit"] = False

        if "first_name" in inp:
            for x in person.keys():
                person[x] = inp[x]
            corpdb.phonebook.save(person)

        pp["person"] = person

        # --- image upload ----

        if "myfile" in inp:
            x = web.input(myfile={})["myfile"]
            gfs = gridfs.GridFS( corpdb )
            fid = gfs.put( x.value , filename = x.filename , user = inp["id"] )
            corpdb.fs.files.create_index( "user" )

        # --- canEdit ----

        canEdit = False

        if pp["user"] == person["jira_username"] or pp["user"] == person["primary_email"]:
            canEdit = True
        else:
            me = corpdb.phonebook.find_one( { "jira_username" : pp["user"] } )
            if me:
                if me["title"] == "CTO":
                    canEdit = True
                if me["areas_of_focus"].find( "hr" ) >= 0:
                    canEdit = True

        pp["canEdit"] = canEdit

urls = (
    "/codeReview/patternTest/(.+)/(.+)/(.+)", CodeReviewPatternTest,
    "/codeReview/rules/(.+)", CodeReviewAssignmentRule,
    "/codeReview/rules", CodeReviewAssignmentRules,
    "/codeReview/commits/(.*)/(.*)", CodeReviewCommits,
    "/codeReview/commit/(.*)", CodeReviewCommit,
    "/codeReview/postReceiveHook", CodeReviewPostReceiveHook,
    "/pstats", Pstats,
    "/pstats/csv", PstatsCSV,
    "/jirarep", JiraReport,
    "/jiramulti", JiraMulti,
    "/engineer/(.*)", JiraEngineerReport,# TODO fix urls
    "/customer/(.*)", JiraCustomerReport,# TODO fix urls
    "/favicon.ico", CorpFavicon,
    '/clienthub', clienthub.views.ClientHub,
    '/clienthub/all', clienthub.views.AllClients,
    '/clienthub/link/(.+)/(.+)', clienthub.views.ClienthubRedirector,
    '/clienthub/view/([^/]+)/export/', clienthub.views.ExportClientView,
    '/clienthub/view/salesforce/([^/]+)', clienthub.views.ClientViewSalesForce,
    '/clienthub/view/([^/]+)', clienthub.views.ClientView,
    '/clienthub/view/([^/]+)/docs/([^/]+)/([^/]+)', clienthub.views.ClientDocView,
    '/clienthub/view/([^/]+)/docs/([^/]+)/([^/]+)/delete', clienthub.views.ClientDocDelete,
    '/clienthub/edit/(.+)', clienthub.views.ClientEdit,
    '/clienthub/view/([^/]+)/uploads/([^/]+)/([^/]+)', clienthub.views.ClientUploadView,
    "/(.*)", CorpNormal,
)





for url, cls in zip(urls[0::2], urls[1::2]):
    app.add_mapping(url, cls)
logfilename = os.path.join(here, 'www-corp.log')
logging.basicConfig(format='%(asctime)s:%(name)s:%(levelname)s:%(message)s', filename=logfilename,level=logging.INFO)
logging.info('Logger up')

if __name__ == "__main__":
    if len(sys.argv) == 1:
        app.run()
    else:
        cmd = sys.argv[1]
        if cmd == "crowdtest":
            for z in eng_group:
                print(z)
                print( "\t" + str( the_crowd.getUser( z ) ) )
        elif cmd == "jiramultitest":
            jm = JiraMulti()
            pprint.pprint( jm.getIssues(sys.argv[2].split( "," )) )
        else:
            print( "unknown www command: " + cmd )
else:
    application = app.wsgifunc()

