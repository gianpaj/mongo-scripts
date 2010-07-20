#!/usr/bin/python

import sys
import socket
from time import strptime , strftime
import re
import datetime
import zlib,gzip
import StringIO

import pymongo

import simples3
import settings # for s3

class LineParser:
    def __init__(self,regex,names):
        self._regex = regex
        self._names = names
        self._patt = re.compile( regex )

    def parse(self,line):
        m = self._patt.match(line)
        if not m:
            print( "can't parse line: " + line )
            return None

        result = [m.group(1+n) for n in range(len(self._names))]

        d = {}
        for ( name , val ) in zip( self._names , result ):
            d[ name ] = val

        return d


normalParser = LineParser( r'(\S+) (\S+) \[(.*?)\] (\S+) (\S+) ' \
                               r'(\S+) (\S+) (\S+) "([^"]+)" ' \
                               r'(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) ' \
                               r'"([^"]+)" "([^"]+)"' , 
                           ("bucket_owner", "bucket", "datetime", "ip", "requestor_id", 
                            "request_id", "operation", "uri-stem", "http_method_uri_proto", "status", 
                            "s3_error", "bytes_sent", "object_size", "total_time", "turn_around_time",
                            "Referer", "User-Agent") )


class W3CParser:
    def __init__(self):
        self.p = re.compile("\s+")

    def parse(self,line):
        if line.startswith( "#Version:" ):
            return None
        
        if line.startswith( "#Fields: " ):
            x = self.p.split( line[9:] )
            self.names = []
            for z in x:
                if z.startswith( "cs-" ):
                    z = z[3:]
                if z.startswith( "cs(" ):
                    z = z[3:]
                    z = z.rstrip( ")" )
                if z.startswith( "c-" ):
                    z = z[2:]
                if z.startswith( "sc-" ):
                    z = z[3:]
                self.names.append( z )
            return None
        
        x = self.p.split( line )

        d = {}
        for ( name , val ) in zip( self.names , x ):
            d[name] = val
        return d
                           

def getAllDays( start=(2009,0) ):
    a = []
    y = start[0]
    today = datetime.datetime.today()
    while y <= today.year:

        maxMonth = 12
        if y == today.year:
            maxMonth = today.month

        minMonth = 0
        if y == start[0]:
            minMonth = start[1]

        for m in range( minMonth , maxMonth ):
            for d in range( 31 ):
                t = (y,m,d)
                a.append( t )

        y = y + 1

    return a

allDays = getAllDays( (2009,1) )

def addGZ( n ):
    return [ n , n + ".gz" ]

badEndings = []
for x in [ "Packages" , "Packages.bz2" , "Release" , "Sources" , 
           ".xml" , ".dsc" , ".md5" , ".gpg" 
           , ".pdf" , ".html" , ".png" , ".conf" ]:
    badEndings.append( x )
    badEndings.append( x + ".gz" )

badStrings = [ "misc/boost" ]

goodEndings = [ ".tar.gz" , ".tgz" , ".zip" , ".deb" , ".rpm" ]


# -1 bad, 0 unknown 1 good
def decide( key ):
    for e in badEndings:
        if key.endswith( e ):
            return -1
    for e in badStrings:
        if key.find( e ) >= 0:
            return -1
    for e in goodEndings:
        if key.endswith( e ):
            return 1
    return 0


def skipLine( data ):
    if data["ip"] == "64.70.120.90":
        return True

    if data["User-Agent"].find( "bot" ) >= 0:
        return True

    if data["status"] != "200":
        return True
       
    key = data["uri-stem"]
    if key == "-" or key.startswith( "log/" ) or key.startswith( "stats/" ):
        return True

    x = decide( key )
    if x < 0:
        return True
    
    if x == 0:
        print( "skipping unknown: " + key )
        return True

    return False


conn = pymongo.Connection()
db = conn.mongousage


def doBucket( fileNameBuilder , parser , start ):

    s = simples3.S3Bucket( settings.bucket , settings.id , settings.key )
    seen = 0

    for y,m,d in getAllDays(start):
        filter = fileNameBuilder( y , m , d )
        print(filter)
        for (key, modify, etag, size) in s.listdir(prefix=filter):
            print( "\t" + key )
            if db.files.find_one( { "_id" : key } ):
                continue

            lineNumber = 0
            
            data = s.get(key).read()
            if key.endswith( ".gz" ):
                data = gzip.GzipFile('', 'rb', 9, StringIO.StringIO(data)).read()

            for line in data.splitlines():
                lineNumber = lineNumber + 1

                p = parser.parse( line )
                if not p:
                    continue

                if skipLine( p ):
                    continue;

                p["_id"] = key + "-" + str(lineNumber)
                p["raw"] = line
                p["date"] = { "year" : y , "month" : m + 1 , "day" : d + 1 }
                p["fromFile"] = key
                p["os"] = p["uri-stem"].partition( "/" )[0]
                db.downloads.insert( p )

            db.files.insert( { "_id" : key , "when" : datetime.datetime.today() } )

def normalFileNameBuilder(y,m,d):
    return "log/access_log-%d-%02d-%02d" % ( y , m + 1 , d + 1 )

def cloudfrontFileNameBuilder(y,m,d):
    return "log-fast/E22IW8VK01O2RF.%d-%02d-%02d" % ( y , m + 1 , d + 1 )

doBucket( normalFileNameBuilder , normalParser , ( 2009 , 1 ) )
doBucket( cloudfrontFileNameBuilder , W3CParser() , ( 2010 , 6 ) )


