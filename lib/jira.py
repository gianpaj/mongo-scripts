# Helpers to handle connecting to JIRA and logging in using SOAP
#
# The settings for the connection / username / password are kept in settings.py

import traceback
import suds.client
import urllib2
import base64
import json
import os
import types
import sys

class JiraConnection(object):
    """Just a wrapper around a suds client that passes through getattr.

    j = JiraConnection()
    j.getUser( "eliot" ) # can call soap methods directly
    
    """
    def __init__(self):
        """On init make a connection to JIRA and login.
        """
        try:
            import settings
            self.__client = suds.client.Client(settings.jira_soap_url)
            self.__auth = self.__client.service.login(settings.jira_username, settings.jira_password)
        except:
            print( "failed to get u/p for jira" )
            self.__client = None
            self.__auth = None

    def __getattr__(self, method):
        """Pass through __getattr__s to underlying client.
        """
        if self.__client is None:
            return None

        a = self.__auth
        m = getattr(self.__client.service, method)

        if m is None:
            return m
        
        def foo(*args):
            return m(a,*args)
        
        return foo

    def __enter__(self):
        """Support for the context manager protocol.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for the context manager protocol.

        Log out of jira. Suppress any exceptions.
        """
        if self.__client is not None:
            self.__client.service.logout(self.__auth)

        if exc_type:
            print "JIRA operation failed:"
            traceback.print_exception(exc_type, exc_val, exc_tb)
            print ""

        return True


class MyAuth(urllib2.BaseHandler):
    def __init__(self,u,p):
        self.enc = "%s:%s" % (u,p)
        
    def default_open(self,r):
        r.add_header( "Authorization" , "Basic %s" % ( base64.b64encode(self.enc).strip() ) )
        

class JiraRest:
    
    def __init__(self,username,passwd,version="2.0.alpha1",host="https://jira.mongodb.org"):
        self.username = username
        self.passwd = passwd

        self.version = version
        self.host = host

        self.opener = urllib2.build_opener( MyAuth( self.username , self.passwd ) )


    def fetch(self,suffix):
        url = "%s/rest/api/%s/%s" % ( self.host , self.version , suffix )
        data = self.opener.open( url )
        data = data.read()
        return json.loads( data )

    def issue(self,key):
        return self.fetch( "issue/" + key )

    def dl_attachment(self,obj,local_dir):
        local_file = local_dir + "/" + obj["content"].partition( "attachment/" )[2].replace( '/' , '_' )
        if os.path.exists( local_file ):
            return
        print( "fetching: " + obj["filename"] )
        f = open( local_file , "wb" )
        f.write( self.opener.open( obj["content"] ).read() )
        f.close()


if __name__ == "__main__":

    if len(sys.argv) <= 1:
        print( "need to tell me what to do" )
        exit(0)
    
    cmd = sys.argv[1]

    j = JiraConnection();
    
    if "upload" == cmd:
        if len(sys.argv) != 4:
            print( "usage: upload <case> <filename>" )
            exit(0)

            
        case = sys.argv[2]
        filename = sys.argv[3]

        if os.path.exists( filename ):
            print( "don't know how to upload a real file" )
        else:
            data = sys.stdin.readlines()
            j.addBase64EncodedAttachmentsToIssue( case , [ filename ] , [ base64.b64encode( "".join( data ) ) ] )


    else:
        print( "unknown command: " + cmd )


