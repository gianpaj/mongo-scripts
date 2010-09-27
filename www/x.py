#!/usr/bin/python

import sys
import os
import suds.client

here = os.path.dirname(os.path.abspath(__file__))

# Suds is a lightweight SOAP python client: https://fedorahosted.org/suds/
# Download .tgz, untar, then install: sudo python setup.py install

# the default crowd .wsdl (http://localhost:8095/crowd/services/SecurityServer?wsdl) 
# has missing import statements, causing suds to fail, so we use a modified local copy
# see http://jira.atlassian.com/browse/CWD-159

# place modified wsdl where the script can access it
#url = 'http://localhost/crowd-fixed.wsdl'
url='file://' + here + '/crowd-fixed.wsdl'


client = suds.client.Client(url)

# crowd application name and password
auth_context = client.factory.create('ns1:ApplicationAuthenticationContext')
auth_context.name = 'corp'
auth_context.credential.credential = 'eng718corp'

token = client.service.authenticateApplication(auth_context)

# print a user's groups
user = 'eliot'
groups = client.service.findGroupMemberships(token, user)
print user + ' groups:'
if len(groups) > 0:
    for g in sorted(groups.string):
        print "  " + g
else:
    print "  <none>"

# try to authenticate
z = client.service.authenticatePrincipalSimple( token , "josh", "josh7" )
try:
    print( client.service.isValidPrincipalToken( token , z , client.factory.create( "ns1:ArrayOfValidationFactor" ) ) )
    print( client.service.isValidPrincipalToken( token , z + "a" , client.factory.create( "ns1:ArrayOfValidationFactor" ) ) )
except Exception,e:
    print(e)
client.service.invalidatePrincipalToken( token , z )


if False:
    # print a group's members
    group = 'jira-users'
    soap_group = client.service.findGroupByName(token, group)
    print
    print group + ' members:'
    if soap_group and soap_group.members:
        for u in sorted(soap_group.members.string):
            print "  " + u
    else:
        print "  <none>"
