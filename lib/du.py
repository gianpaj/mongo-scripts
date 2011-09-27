
import crowd 
import sys
import os
import pymongo
import gmail
import datetime
import pprint
from BeautifulSoup import BeautifulSoup

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
        u["last_reminder"] = datetime.datetime.now() - datetime.timedelta(1)
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

    def send_report(self):
        emailbody = "Hello 10gen Management,\nHere's a summary of how many DUs everyone sent this week:\n\n"
        weekago = datetime.datetime.utcnow() - datetime.timedelta(7)
        for user in self.getUsers():
            if "skip" in user and user["skip"]:
                continue
            username = user["_id"]
            numdus = self.dus.find({"user":username, "headers.date" : {"$gt" : weekago}}).count()
            emailbody += "%s: %d\n" % (username, numdus)
        self.gmail.send_simple("techmgmt@10gen.com", "Weekly DU report", emailbody, replyto="noreply@10gen.com")

    def send_reminder(self,user):


        self.gmail.send_simple( user["mail"] , 
                                "Time for your DU - %s - %s" % ( user["_id"] , datetime.date.today().strftime( "%D" ) ) , 
                                "*** What did you do today?\n" +
                                "*** What are you planning on doing tomorrow?\n" +
                                "*** What blockers do you have?\n" +
                                "\n"
                                "Please reply to this email with your DU\n" +
                                "Should go only to dus@10gen.com, do not send to dev\n" +
                                "Web interface at: http://www.10gen.com/admin/dumanager\n"
                                , replyto="dus@10gen.com" )

        self.users.update( { "_id" : user["_id"] } , { "$set" : { "last_reminder" : datetime.datetime.now() } } )

    def send_reminders(self):
        for user in self.getUsers():
            print( "send_reminders checking: " + user["_id"] )

            if "skip" in user and user["skip"]:
                continue

            # TODO: this should be utcnow()?
            diff = datetime.datetime.now() - user["last_reminder"]
            diff = diff.seconds + ( 24 * 3600 * diff.days )
            print( "\t last reminder: %s - %d seconds ago" % ( str(user["last_reminder"]) , diff ) )

            # if last reminder was sent less than 12 hours ago,
            # skip user for now
            if diff < ( 3600 * 12 ):
                continue;

            # take into account user's gmt offset, and send email to them if it's at or
            # after their desired reminder time in their configured local time
            curtime = datetime.datetime.utcnow()
            reminderTime = user.get('reminderTime', '17:00') # Default to 5pm
            reminderTime = datetime.datetime.strptime(reminderTime, "%H:%M").time()

            modhour = curtime.hour
            if "gmtoffset" in user:
                modhour = modhour + int(user["gmtoffset"])
                if modhour < 0:
                    modhour = modhour + 24
            print( "\t cur hour: %d  modhour: %d cur minute: %d" % ( curtime.hour , modhour , curtime.minute ) )
            print( "\t reminder hour: %d reminder minute: %d" % (reminderTime.hour, reminderTime.minute) )

            modtime = reminderTime.replace(hour=modhour, minute = curtime.minute)
            if modtime < reminderTime:
                continue

            print( "\t sending reminder to: " + user["mail" ] )
            self.send_reminder( user )

    def _store(self,msg):
        sub = msg["headers"]["subject"]
        date = msg["headers"]["date"]

        f = msg["headers"]["from"]
        u = None
        user = None

        if sub.find( "-" ) >= 0:
            user = sub.split( "-" )[1].strip();
            u = self.getUser( user )

        if u == None and f.find( "<" ) >= 0:
            f = f.partition( "<" )[2].partition( ">" )[0]
            u = self.users.find_one( { "mail" : f } )
            
            if u == None:
                u = self.users.find_one( { "aliases" : f } )

            if u != None:
                user = u["_id"]
        
        if u == None:
            raise Exception( "can't find user subject [%s] from [%s] user [%s]" % ( sub , f , str(user) ) )

        self.users.update( { "_id" :user } , { "$set" : { "last_du" : date } } )

        msg["user"] = user

        # Don't insert DU if it's already in the database
        if self.dus.find_one({'user':user, 'headers.subject':sub, 'headers.message-id':msg['headers']['message-id']}):
            return
        
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

        usernames = []
        for user in messages:
            usernames.append( user )

        usernames.sort()

        for user in usernames:
            lst = messages[user]
            body += "%s\n" % user
            for m in lst:
                body += tab(1) + str(m["headers"]["date"]) + "\n"
                
                b = m["body"]
                if not isinstance( b , basestring ):
                    if "text/plain" in b:
                        b = b["text/plain"]["body"]
                    else:
                        b = "".join(BeautifulSoup(b["text/html"]["body"]).findAll(text=True))

                for l in b.split( "\n" ):
                    l = l.rstrip()
                    if l.startswith( ">" ) and l.find( "***" ) < 0:
                        continue
                    if l.endswith( "wrote:" ):
                        continue
                    body += tab(2) + l + "\n"
                

        if body == "":
            print( "no summary to send" )
            return


        missing = []
        for u in self.users.find( { "skip" : { "$ne" : True } } ):
            if u["_id"] not in messages:
                missing.append( u["_id"] )
                
        if len(missing) > 0:
            body += "\nmissing: " + " ".join( missing ) + "\n"
        body += "\n"
        print( body )

        self.gmail.send_simple( "dusummary@10gen.com" , "DU Summary for %s" % datetime.date.today().strftime( "%D" ) , 
                                body , replyto="dev@10gen.com" )

        self.dus.update( { "_id" : { "$in" : ids } } , { "$set" : { "sent" : True } } , multi=True )

if __name__ == "__main__":
    
    du = DU()

    if len(sys.argv) == 1:
        raise Exception( "need a command for now" )
               
    cmd = sys.argv[1]

    # main commands
    if cmd == "send_summary":
        du.fetch()
        du.send_summary();
    elif cmd == "send_reminders":
        du.send_reminders()
    elif cmd == "fetch":
        du.fetch()
    elif cmd == "send_report":
        du.send_report()
    # debug commands
    elif cmd == "getUserNames":
        for x in du.getUserNames():
            print( x )
    elif cmd == "list":
        for x in du.getUsers():
            print( x )
    elif cmd == "gmail_test":
        du.gmail.send_simple( "eliot@10gen.com" , "test" , "test body" , replyto="dus@10gen.com" )

    # catch all
    else:
        print( "unknown du command: " + cmd )
