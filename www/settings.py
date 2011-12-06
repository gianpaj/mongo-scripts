from settings_private import (
    crowdAppUser,
    crowdAppPassword,
    smtp,
    salesforce,
    )

import os
here = os.path.dirname(os.path.abspath(__file__))
devel = os.path.exists(os.path.join(here, 'devel'))

if devel:
    usagedb_host = wwwdb_host = mongowwwdb_host = "localhost"
else:
    usagedb_host = "jira.10gen.cc"
    wwwdb_host = "localhost"
    mongowwwdb_host = "localhost"
    jirareports_host = "localhost"

#Jira
jira_soap_url = "http://jira.mongodb.org/rpc/soap/jirasoapservice-v2?wsdl"
jira_username = "auto"
jira_password = "automenow"
jira_support_group = "Commercial Support"
