import os
import sys
#import pymongo
import pprint
import re
import urllib2
import time
import datetime
import traceback
import math
import types
import time

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0]
sys.path.append( path )
pp = pprint.PrettyPrinter(depth=6)

import lib.gmail
import lib.googlegroup
import lib.jira
import lib.crowd
import lib.aws

import settings

import suds.sudsobject

from pymongo import Connection
connection = Connection()
db = connection.jira

def pythonify_suds_obj(obj):
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
   return objdict


class Processor:
    def __init__(self):
        self.total = 0
        self.slices = {}

    def process(self,issue,comments):
        self.total = self.total + 1

        sliceName = "%s-%s" % ( issue["updated"].year , issue["updated"].month )
        if sliceName not in self.slices:
            self.slices[sliceName] = TimeSlice(sliceName)
        slice = self.slices[sliceName]

        slice.process( issue , comments )

    def display(self):
        print( "total: %s" % self.total )
        for x in self.slices:
            print( "\t%s" % x )
            self.slices[x].display()

class Retreiver:
    def __init__(self):
        self.limit = 2000
        self.batchSize = 10
        self.counter = 1
        self.projectName = "CS"
        self.issues = { }
        self.jira = lib.jira.JiraConnection()

    def retreiveSet( self, jql ):
        try:
            for issue in self.jira.getIssuesFromJqlSearch( jql, self.batchSize ):
                issue["comments"] = self.jira.getComments( issue["key"] )
                issue["resolutiondate"] = self.jira.getResolutionDateByKey(issue["key"])
                self.issues[issue["key"]] = self.fixCustomFields(issue)

        except suds.WebFault as detail:
            print detail
            #If a issue is missing, iterate through 1 at a time.
            i = self.counter
            while i < self.counter + self.batchSize:
                try:
                    for issue in self.jira.getIssuesFromJqlSearch( "%s AND key = %s-%i" % (self.baseJQL, self.projectName, i), 1 ):
                        issue["comments"] = self.jira.getComments( issue["key"] )
                        self.issues[issue["key"]] = self.fixCustomFields(issue)
                except suds.WebFault as detail2:
                    print detail2
                    pass
                i = i+1

    def fixCustomFields(self, issue):
        for cs in issue["customFieldValues"]:
            name = db.customfields.find_one({ "_id" : cs.customfieldId})
            issue[name["name"]] = cs.values
        del issue.customFieldValues
        return issue

    def retreiveRecent(self, jql):
        self.updateCustomFields()
        self.baseJQL = jql
        yesterday = (datetime.datetime.now() - datetime.timedelta(days=2)).timetuple()
        query =  "%s AND updated >= %s" % ( jql, time.strftime("%Y-%m-%d", yesterday) )
        self.retreiveSet(query)
        time.sleep(1)
        self.counter = self.counter + self.batchSize

    def retreive( self, jql ):
        self.updateCustomFields()
        self.baseJQL = jql
        while self.counter < self.limit:
            query =  "%s AND key >= %s-%i AND key < %s-%i" % ( jql, self.projectName, self.counter, self.projectName, self.counter + self.batchSize)
            print query
            self.retreiveSet(query)
            time.sleep(1)
            self.counter = self.counter + self.batchSize

    def display( self):
        #print( "total: %i" % self.issues.len)
        #pp.pprint(self.issues)
        for k,v in self.issues.items():
            pp.pprint( x )

    def storeIssue( self, issue ):
        i = pythonify_suds_obj(issue)
        i['_id'] = i['key']
        print "saving issue:", i['key']
        db.issues.save(i)

    def store(self):
        for k,v in self.issues.items():
            self.storeIssue(v)

    def updateCustomFields(self):
        for field in self.jira.getCustomFields():
            #pp.pprint(field)
            field["_id"] = field["id"]
            db.customfields.save(pythonify_suds_obj(field))

def run( retreiver, jql ):
    retreiver.retreive( jql )


def main(args):
  if "--recent" in args:
    retreiver = Retreiver()
    retreiver.retreiveRecent("project = CS AND type != Tracking")
    retreiver.store()
    retreiver.updateCustomFields()
  else:
    retreiver = Retreiver()
    run( retreiver, "project = CS AND type != Tracking" )
    retreiver.store()
    retreiver.updateCustomFields()


if __name__ == '__main__': main(sys.argv[1:])
