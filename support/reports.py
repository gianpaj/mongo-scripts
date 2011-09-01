


import os
import sys
import pymongo
import pprint
import re
import urllib2
import time
import datetime
import traceback
import math

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0] 
sys.path.append( path )

import lib.gmail
import lib.googlegroup
import lib.jira
import lib.crowd
import lib.aws

import settings

class ExpoentialBucket:
    def __init__(self):
        self.buckets = []

    def hit(self,value):
        bucket = int(math.log(value))
        while bucket >= len(self.buckets):
            self.buckets.append( ( 0 , 0 ) )

        old = self.buckets[bucket]
        self.buckets[bucket] = ( value + old[0] , 1 + old[1] )

    def display(self,prefix):
        for x in range(0,len(self.buckets)-1):
            print( "%s %d: %d" % ( prefix , x , self.buckets[x][1] ) )
        

class TimeSlice:
    def __init__(self,name):
        self.name = name
        self.total = 0

        self.firstCommentTime = ExpoentialBucket()

    def process(self,issue,comments):
        self.total = self.total + 1

        if len(comments) > 0:
            td = comments[0]["created"] - issue["created"]
            minutesForFirstComment = ((td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6)/60

            self.firstCommentTime.hit(minutesForFirstComment)

    def display(self):
        print( "\t\t total: %d" % self.total )
        print( "\t\t minutes for first comment" )
        self.firstCommentTime.display( "\t\t\t" )

class Aggregrator:
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


def run( aggregrator ):
    jira = lib.jira.JiraConnection()
    for issue in jira.getIssuesFromJqlSearch( "project = CS AND type != Tracking" , 1000 ):
        aggregrator.process( issue , jira.getComments( issue["key"] ) )

        
aggregrator = Aggregrator()
run( aggregrator )
aggregrator.display()    
    
