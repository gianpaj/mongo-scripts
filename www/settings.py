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
    jirareports_host = pstats_host = usagedb_host = wwwdb_host = mongowwwdb_host = corpdb_host = "localhost"
else:
    usagedb_host = "jira.10gen.cc"
    wwwdb_host = "localhost"
    mongowwwdb_host = "localhost"
    jirareports_host = "localhost"
    corpdb_host = "localhost"
    pstats_host = 'mongo05.10gen.cust.cbici.net'
    fts_host = 'www-c3.10gen.cc'

#Jira
jira_soap_url = "http://jira.mongodb.org/rpc/soap/jirasoapservice-v2?wsdl"
jira_username = "auto"
jira_password = "automenow"
jira_support_group = "Commercial Support"
pstats_username = 'perf'
pstats_password = 'powerbook17'



