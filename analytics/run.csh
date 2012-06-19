#!/bin/csh

/usr/bin/python /jira/corp/analytics/update.py 
/jira/mongo/current/bin/mongo --host stats.10gen.cc /jira/corp/analytics/roundup.js  
/usr/bin/python /jira/corp/analytics/sendSummary.py >& /tmp/ss11
