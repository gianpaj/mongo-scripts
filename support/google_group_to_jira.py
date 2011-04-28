
import os
import sys
import pymongo
import pprint
import re
import urllib2
import time
import datetime

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0] 
sys.path.append( path )

import lib.gmail
import lib.googlegroup
import lib.jira
import lib.crowd
import lib.aws

import settings

def send_error_email(msg):
    lib.aws.send_email( "noc-admin@10gen.com" , "Free Support Tool Error" , str(msg) , "noc-admin@10gen.com" )

class ggs:
    def __init__(self):
        self._gmail = None
        
        # setup mongo
        self.db = pymongo.Connection().support_gg
        self.processed = self.db.processed

        self.topics = self.db.topics
        self.topics.ensure_index( "subject" )
        self.topics.ensure_index( "url" )

        self.gg_threads = self.db.gg_threads
        self.gg_threads.ensure_index( "subject" )
        self.gg_threads.ensure_index( "subject_simple" )

        self.users = self.db.users
        self.users.ensure_index( "mail" )
        
        # setup some regex
        self.topic_cleaners = [ "re:" , "fwd:" , "\[mongodb-[a-z]+\]" ]
        self.topic_cleaners = [ re.compile( x , re.I ) for x in self.topic_cleaners ]

        # gg parser
        self.gg = lib.googlegroup.GoogleGroup( "mongodb-user" )
        
        # crowd
        self.crowd = lib.crowd.Crowd( settings.crowdAppUser , settings.crowdAppPassword )
        self.sync_users()
        
    def sync_users(self):
        for u in self.crowd.findGroupByName( "10gen" ):
            if self.getUser( u ):
                continue
            z = self.crowd.getUser( u )
            z["_id"] = z["username"]
            z["mail"] = [ z["mail"] ]
            del z["username"]
            
            self.users.insert( z )

    def getUser(self,username):
        return self.users.find_one( { "_id" : username } )


    def getUserByMail(self,mail):
        return self.users.find_one( { "mail" : mail } )        

    def clean_topic(self,s):
        for x in self.topic_cleaners:
            s = x.sub( "" , s )
        s = s.strip()
        s = re.sub( "\s\s+" , " " , s )
        return s

    def simple_topic(self,s):
        s = self.clean_topic( s )
        s = re.sub( "\s*" , "" , s )
        s = s.lower()
        return s


    def sync(self):
        error = False
        msg = { "_id" : str(datetime.datetime.utcnow()) }
        start = time.time()        
        stats = {}
        try:
            stats["mail"] = self.sync_mail()
            stats["topics"] = self.sync_subjects()
            stats["urls"] = self.sync_urls()
            stats["jira"] = self.sync_jira()
        except Exception,e:
            print(e)
            msg["error"] = str(e)
            error = True

        msg["stats"] = stats
        end = time.time()
        msg["elapsedSeconds"] = end - start;

        self.db.log.insert( msg )
        
        self.db.stats.update( { "_id" : str(datetime.datetime.utcnow())[0:13] } , { "$inc" : stats } , upsert=True )

        if error:
            send_error_email(str(e))

        
    def gmail(self):
        if not self._gmail:
            self._gmail = lib.gmail.gmail( "info@10gen.com" , "eng718info" )
            self._gmail.select( "freesupport" )
        return self._gmail

    def sync_mail(self):
        num = 0
        all = self.gmail().list()
    
        for x in all:
            m = self.gmail().fetch ( x )
            headers = m["headers"]
            key = headers["message-id"]
            
            if self.processed.find_one( { "_id" : key } ):
                continue
            
            num = num + 1
            p = { "_id" : key , "uid" : x }
            for z in [ "from" , "subject" , "date" ]:
                p[z] = headers[z]
                
            ids = []
            for z in [ "in-reply-to" , "message-id" , "references" ]:
                if z in headers:
                    if isinstance( headers[z], list):
                        ids += headers[z]
                    else:
                        ids.append( headers[z] )

            print( ids  )
            
            self.topics.update( { "ids" : { "$in" : ids } } , 
                                { "$addToSet" : { "ids" : { "$each" : ids } ,
                                                  "messages" : p } } ,
                                upsert=True )

            self.processed.insert( p )

        return num

    def sync_subjects(self):
        num = 0
        for x in self.topics.find( { "subject" : None } ):
            sub = None
            for m in x["messages"]:
                s = m["subject"]
                s = self.clean_topic( s )

                if sub is None:
                    sub = s
                elif sub != s:
                    a = re.sub( "\s+" , "" , sub )
                    b = re.sub( "\s+" , "" , s )
                    if a != b:
                        pprint.pprint( m )
                        print( "warning: [%s] != [%s]" % ( sub , s ) )

            print( sub )
            self.topics.update( { "_id" : x["_id"] } , { "$set" : { "subject" : sub , "subject_simple" : self.simple_topic( sub ) } } )
            num = num + 1
        return num

    def _pull_url(self,url,others):
        detail = self.gg_threads.find_one( { "_id" : url } )
        if detail:
            return False

        detail = self.gg.getThreadDetail( url , others )
        detail["_id"] = url
        detail["subject"] = self.clean_topic( detail["subject"] )
        detail["subject_simple"] = self.simple_topic( detail["subject"] )
        self.gg_threads.insert( detail )
        #print( "%s\n\t%s" % ( url , detail["subject"] ) )        
        return True

    def pull_urls(self,pages_back=1):
        threads = self.gg.getThreads( pages_back )
        print( len(threads) )
        
        others = set()

        for x in threads:
            self._pull_url( x , others )

        for x in others:
            if self._pull_url( x ,None ):
                print( "found via ll: %s" % x )

    def sync_urls(self,iteration=0):
        num = 0
        numMissing = 0
        for x in self.topics.find( { "url" : None } ):
            if "skip" in x and x["skip"]:
                continue

            lst = list(self.gg_threads.find( { "subject" : x["subject"] } ))
            ss = x["subject_simple"]
            if len(lst) == 0:
                lst = list(self.gg_threads.find( { "subject_simple" : ss } ))
            
            if len(lst) == 0 and ss.find( "]" ) >= 0 :
                even_cleaner = x["subject_simple"].rpartition( "]" )[2]
                lst = list(self.gg_threads.find( { "subject_simple" : even_cleaner } ))
                
            if len(lst) == 0:
                numMissing = numMissing + 1
                print( "missing url for id: %s subject: %s" % ( x["_id"] , x["subject"] ) )
                continue

            if len(lst) > 1:
                raise Exception( "ahhhh 2 topics with same name %s" % x["subject"] )

            ggt = lst[0]
            self.topics.update( { "_id" : x["_id"] } , { "$set" : { "url" : ggt["_id"] } } )
            self.gg_threads.update( { "_id" : ggt["_id"] } , { "$set" : { "topic" : x["_id"] } } )
            num = num + 1

        print( "numMissing: %d" % numMissing )
        if numMissing > 0 and iteration < 5:
            self.pull_urls( iteration + 1 )
            self.sync_urls( iteration + 1 )
            
        return num

    def getUsername(self,email):
        
        if email.find( "<" ) >= 0:
            email = email.rpartition( ">" )[0].rpartition( "<" )[2]

        u = self.getUserByMail( email )
        if u:
            return u["_id"]
        
        return None

    def cleanComment(self,cmt):
        if "text/plain" in cmt:
            return self.cleanComment( cmt["text/plain"] )
        elif "text/html" in cmt:
            cmt = cmt["text/html"]
            cmt = cmt.replace( "<br>" , "\n" )
            cmt = re.sub( ">\s+<" , "><" , cmt )
            cmt = re.sub( "<.*?>" , "" , cmt )
            return self.cleanComment( cmt )
        elif "body" in cmt:
            return self.cleanComment( cmt["body"] )

        cmt = str(cmt)
        cmt = cmt.partition( "You received this message because you are subscribed to the Google Groups" )[0]

        n = ""
        prevSkipped = False
        for line in cmt.split( "\n" ):
            if line.startswith( ">" ):
                if not prevSkipped:
                    n += " ----  SKIPPING LINES ----\n"
                    prevSkipped = True
                continue
            n += line + "\n"
            prevSkipped = False

        return n.strip()
        

    def sync_jira(self):
        num = 0 
        def debug(msg):
            if True:
                print(msg)

        j = lib.jira.JiraConnection()

        for x in self.topics.find( { "url" : { "$ne" : None } } ):
            if "skip" in x and x["skip"]:
                continue

            debug( x["subject"] )

            key = None
            if "jira" in x:
                key = x["jira"]
                
            if key is None:
                debug( "\t need to add to jira" )
                url = x["url"]
                if url.find( "http://" ) != 0:
                    url = "http://groups.google.com" + url

                res = j.createIssue( { "project" : "FREE" , 
                                       "type" : "1" , 
                                       "summary" : x["subject"] ,
                                       "description" : url } )
                key = res["key"]
                debug( "\t new key: %s" % key )
                self.topics.update( { "_id" : x["_id"] } , { "$set" : { "jira" : key } } )
                x["jira"] = key
            
                
            issue = j.getIssue( key )
            assignee = issue["assignee"]
            debug( "\t https://jira.mongodb.org/browse/%s" % key )
            debug( "\t currently assigned to [%s]" % assignee )
            #print( issue )
                
            needToSave = False

            user = None
            for m in x["messages"]:
                if "processed" in m and m["processed"]:
                    continue
                
                cmt = "%s\n%s\n" % ( m["from"] , m["date"] )

                email = self.gmail().fetch( m["uid"] )
                if email and "body" in email:
                    email = email["body"]
                    cmt += self.cleanComment( email )

                needToSave = True
                m["processed"] = True
                
                user = self.getUsername( m["from"] )
                if assignee is None and user is not None:
                    debug( "\t going to assign to %s" % user )
                    j.updateIssue( key , [ { "id" : "assignee" , "values" : [ user ] } ] )
                    assignee = user
                    
                debug( "\t adding comment from %s" % m["from"] )

                if user is None:
                    j.addComment( key , { "body" : cmt } )
                
            def progress( to ):
                if issue["status"] == to:
                    return None
                debug( "\t progressing from %s to %s" % ( issue["status"] , to ) )
                return j.progressWorkflowAction( key , to )

            if user:
                # this means the last comment was from a 10gen person
                if issue["status"] == "1":
                    progress( "21" )
            elif needToSave:
                if issue["status"] == "1":
                    # this is ok
                    pass
                elif issue["status"] == "10006":
                    progress( "71" )
                else:
                    progress( "81" )

            if needToSave:
                debug( "\t need to save" )
                self.topics.save( x )
                num = num + 1
        return num



if __name__ == "__main__":

    if len(sys.argv) == 1:
        print( "running normnal sync" )
        try:        
            thing = ggs()
            thing.sync()
        except Exception,e:
            print( e )
            send_error_email(str(e))

    elif "test" == sys.argv[1]:
        print( "testing" )
        thing = ggs()
        

        print( thing.cleanComment( """
a
b
> d
> e
"""
                                 ) )

        print( thing.cleanComment( { "text/html" : """
<html>
 <body>
 a<br>b
 d
 e
 </body>
</html>

""" 
} ) )
    else:
        print( "unknown command: %s" % argv[1] )

