mongo-scripts
======

A collection of various scripts. For now just to benchmark MongoDB.

many_databases_test.js
-------

This script has been specifically written to benchmark MongoDB with a large number of databases. The number of Documents will be spread around Databases. Make sure you keep that consistent, as well as to the num of operations.

    usage: mongo
    	   --eval 'var numDbs = 5000; var numOps = 500; var numDocs = 1000000; var numCols = 10;'
    	   many_databases_test.js
    	   --shell