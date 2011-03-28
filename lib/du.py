
import crowd 
import sys
import os
import pymongo
import gmail
import datetime
import pprint

path = os.path.dirname(os.path.abspath(__file__))
path = path.rpartition( "/" )[0] + "/www"
sys.path.append( path )

import settings

class DU:
    def __init__(self):
        self.crowd = crowd.Crowd( settings.crowdAppUser , settings.crowdAppPassword )

        # gmail
        self.gmail = gmail.gmail( settings.smtp["smtp_username"] , settings.smtp["smtp_password"] )

        # mongo
        self.db = pymongo.Connection().du
        self.dus = self.db.dus
        self.users = self.db.users

        

    def getUser(self,username):
        u = self.users.find_one( { "_id" : username } )
        if u != None:
            return u

        u = self.crowd.getUser( username )
        if u == None:
            raise Exception( "can't find user: " + str(username) )
        
        u["_id"] = username
        # TODO add other fields?

        self.users.insert( u , safe=True )
        return u
                
    def getUserNames(self):
        return self.crowd.findGroupByName( "10gen-eng" )

    def getUsers(self):
        users = []
        
        for un in self.getUserNames():
            if un.endswith( "-admin" ) or un.startswith( "crucible" ):
                continue
            u = self.getUser( un )
            users.append( u )

        return users

    def send_reminder(self,user):
        self.gmail.send_simple( user["mail"] , 
                                "Time for your DU - %s - %s" % ( user["_id"] , datetime.date.today().strftime( "%D" ) ) , 
                                "Please reply to this email with your DU\n" +
                                "Should go to dus@10gen.com\n"
                                , replyto="dus@10gen.com" )

    def send_reminders(self):
        for user in self.getUsers():
            print( "sending reminder to: %s \t %s " % ( user["_id"] , user["mail" ] ) )
            self.send_reminder( user )

    def _store(self,msg):
        sub = msg["headers"]["subject"]
        date = msg["headers"]["date"]

        user = sub.split( "-" )[1].strip();

        print( str(date) + "\t" + user )
        print( msg["body"] )

        if self.users.find_one( { "_id" : user } ) == None:
            print( "can't find user: " + user )
            return

        self.users.update( { "_id" :user } , { "$set" : { "last_du" : date } } )

        msg["user"] = user
        
        key = date.strftime( "%Y-%m-%d" ) + "-" + user + "-" + str(date) + "-" + sub
        msg["_id"] = key
        msg["sent"] = False
        self.dus.insert( msg )

    def fetch(self):
        self.gmail.select( "eng dus" )
        for uid in self.gmail.list():
            self._store( self.gmail.fetch( uid ) )
            

    def send_summary(self):
        
        ids = []

        messages = {}

        for msg in self.dus.find( { "sent" : False } ):
            ids.append( msg["_id" ] )

            user = msg["user"]

            if user in  messages:
                messages[user].append( msg )
            else:
                messages[user] = [ msg ]
        
            
        def tab(l):
            s = ""
            for x in range(0,4*l):
                s += " "
            return s

        body = ""

        for user in messages:
            lst = messages[user]
            body += "%s\n" % user
            for m in lst:
                body += tab(1) + str(m["headers"]["date"]) + "\n"
                for l in m["body"].split( "\n" ):
                    l = l.rstrip()
                    if l.startswith( ">" ):
                        continue
                    if l.endswith( "wrote:" ):
                        continue
                    body += tab(2) + l + "\n"
                

        if body == "":
            print( "no summary to send" )
            return

        print( body )
        self.gmail.send_simple( "eliot@10gen.com" , "DU Summary for %s" % datetime.date.today().strftime( "%D" ) , 
                                body , replyto="dev@10gen.com" )

        self.dus.update( { "_id" : { "$in" : ids } } , { "$set" : { "sent" : True } } , multi=True )

if __name__ == "__main__":
    
    du = DU()

    if len(sys.argv) == 1:
        raise Exception( "need a command for now" )
               
    cmd = sys.argv[1]

    # main commands
    if cmd == "send_summary":
        du.send_summary();
    elif cmd == "send_reminders":
        du.send_reminders()
    elif cmd == "fetch":
        du.fetch()
        
    # debug commands
    elif cmd == "list":
        for x in du.getUsers():
            print( x )
    elif cmd == "gmail_test":
        du.gmail.send_simple( "eliot@10gen.com" , "test" , "test body" , replyto="dus@10gen.com" )

    # catch all
    else:
        print( "unknown du command: " + cmd )
