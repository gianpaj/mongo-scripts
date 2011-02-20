#!/bin/bash

/usr/bin/python /jira/corp/analytics/update.py && /jira/mongo/current/bin/mongo /jira/corp/analytics/roundup.js  && /usr/bin/python /jira/corp/analytics/sendSummary.py
