
import csv
import os
import sys
import pprint

import pymongo

here = os.path.dirname(os.path.abspath(__file__))
here = here.rpartition( "/" )[0]
sys.path.append( here )
here = here.rpartition( "/" )[0]
sys.path.append( here + "/lib" )

import settings



def get_email_to_crowd():

    coll = pymongo.Connection().test.people
    
    map = coll.find_one()
    if map:
        return map["map"]

    import crowd

    map = {}

    my_crowd = crowd.Crowd( settings.crowdAppUser , settings.crowdAppPassword )
    for username in my_crowd.findGroupByName( "10gen" ):
        o = my_crowd.getUser( username )
        map[ o["mail"] ] = username


    coll.update( { "_id" : 1 } , { "_id" : 1 , "map" : map } , upsert=True )
        
    return map

email_to_crowd = get_email_to_crowd()

print( email_to_crowd )


headers = None

def fixHeaders( raw ):

    prev = [None]
    
    def fix(n):
        if n == "" and prev[0] == "intercall_code":
            return "intercall_pin"

        n = n.lower()
        n = n.replace( ' ' , '_' )
        n = n.replace( '/' , '' )
        n = n.partition( "(" )[0]
        
        if n == "intercall_code_and_pin_":
            n = "intercall_code"
        prev[0] = n
        return n
    return [ fix(x) for x in raw ]
    

def find_jira_username( user ):
    for f in [ "primary_email" , "primary_chat" ]:
        if f not in user:
            continue
        k = user[f]
        if k in email_to_crowd:
            return email_to_crowd[k]
    return None


corpdb = pymongo.Connection(settings.corpdb_host).corp
phonebook = corpdb.phonebook

for row in csv.reader( open( os.getenv( "HOME" ) + "/Downloads/10gen Employee Contacts - Employee Contact Info.csv" ) ):
    if len(row) == 0:
        continue
    
    if headers == None:
        headers = fixHeaders( row )
        continue

    user = {}

    for n,v in zip(headers,row):
        user[n] = v
        

    if "jira_username" not in user or len(user["jira_username"]) == 0:
        user["jira_username"] = find_jira_username( user )
    
        
    if "primary_email" not in user or len(user["primary_email"]) == 0:
        if "primary_chat" in user and user["primary_chat"].find( "@10gen.com" ) > 0:
            user["primary_email"] = user["primary_chat"]
        elif user["secondary_email"] == "allyson.gee@gmail.com":
            user["primary_email"] = "allyson@10gen.com"
        else:
            pprint.pprint( user )
            raise Exception( "sad" )


    for n in headers:
        if n not in user:
            user[n] = None

    user["_id"] = user["primary_email"]

    phonebook.save( user )
