
import imaplib
import keyring
import getpass

import pymongo

class gmail:
    def __init__(self,emailaddr,pwd,mongo_host="127.0.0.1"):
        self.emailaddr = emailaddr
        self.pwd = pwd;
        
        self.mailbox = imaplib.IMAP4_SSL( "imap.gmail.com" , 993 )
        self.mailbox.login( emailaddr , pwd )

        self.select( "INBOX" )

        self.mongo = pymongo.Connection( mongo_host )
        self.cache = self.mongo.gmail_cache_raw.cache
        
    def select(self,name):
        self.mailbox.select( name )
        self.folder = name

    def list(self):
        res = self.mailbox.uid( "search" , "ALL" )
        return res[1][0].split()

    
    def fetch(self,uid):
        key = self.emailaddr + "-" + self.folder + "-" + str(uid)
        
        raw = self.cache.find_one( { "_id" : key } )
        if raw:
            return raw["data"]

        typ, data = self.mailbox.uid( "fetch" , uid, '(RFC822)')
        if typ != "OK":
            raise Exception( "failed loading uid: %s typ: %s" % ( str(uid) , str(typ) ) )

        self.cache.insert( { "_id" : key , "data" : data } )
        return data
