mongo-scripts
======

A collection of various scripts. For now just to benchmark MongoDB.

many_databases_test.js
-------

This script has been specifically written to test MongoDB (not benchmark) with a large number of databases. The number of Documents will be spread around Databases. Make sure you keep that consistent, as well as to the num of operations.

    usage:
    mongo
    --eval 'var numDbs = 5000; var numOps = 500; var numDocs = 1000000; var numCols = 10;'
    many_databases_test.js
    --shell
    	   

rlogtail.sh
-------

Script to tail a mongo(d|s) log file from the last Restart. It basically find the word RESTARTED and tails the oplog that line.

    usage:
    rlogtail.sh mongoX.log