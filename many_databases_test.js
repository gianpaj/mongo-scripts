var numDbs  = numDbs  || 5000;
var numOps  = numOps  || 500;
var numDocs = numDocs || 1000000;
var numCols = numCols || 10;

// by default   20 = 1000000 / 5000   / 10
var numDocsPerColl = numDocs / numDbs / numCols;

var complexDoc = {'product_name': 'Soap', 'weight': 22, 'weight_unit': 'kilogram', 'unique_url': 'http://amazon.com/soap22', 'categories': [{'title': 'cleaning', 'order': 29}, {'title': 'pets', 'order': 19}], 'reviews': [{'author': 'Whisper Jack','message': 'my dog is still dirty, but i`m clean'}, {'author': 'Happy Marry','message': 'my cat is never been this clean'}]};

var opsColl = db.getSisterDB('manydbtest')['ops'];

// Create databases, insert documents
// and prepare 2 operations to benchmark on that last document
function insert_and_form_operations (mongodb) {
    opsColl.drop();

    for ( i = 0; i < numDbs; i++ ) {
        var findOp =  {
            "op" : "findOne"
        };
        var updateOp = {
            "op" : "update"
            // field names cannot start with $
            // "update" : { "$inc" : { "weight" : 1 } }
        };

        var db = mongodb.getSisterDB('boom-' + i);
        // drop every database 'boom-*'
        db.dropDatabase();

        for (var y = 0; y < numCols; y++) {
            var bulkInsert = [];
            var bulkOpsInsert = [];
            
            coll = db['boom-'+ y];

            findOp.ns = coll.toString();
            updateOp.ns = coll.toString();

            for (var j = 0; j < numDocsPerColl; j++) {
                // insert docs in each db
                complexDoc._id = new ObjectId();
                bulkInsert.push(complexDoc);

                var query = { "_id" : complexDoc._id };

                findOp.query = query;
                updateOp.query = query;
                bulkOpsInsert.push(findOp);
                bulkOpsInsert.push(updateOp);
            }
            opsColl.insert(bulkOpsInsert);
            coll.insert(bulkInsert);
        }
    }
}

// this function finds the operations saved in our temporary 'manydbtest.ops' db.collection
// and add the to ops array
function retrieve_operations () {
    // prepare operations to benchmark
    var operations = opsColl.find().toArray();

    // because field names cannot start with $ - add it here
    for (var i = 0; i < operations.length; i++) {
        if ( operations[i]['op'] == "update" ) {
            operations[i] = operations[i]['update'] = { "$inc" : { "weight" : 1 } };
        }
    }
    return operations;
}

// actual benchmark function
function benchmark () {
    // start from the original operations array and find other x (numOps) no. random of ops
    ops = retrieve_operations();

    // remove randomly operations that will be benchmarked until only the numOps remain (ie. 100)
    var newarray=[];
    while (newarray.length < numOps) {
        rnd = Math.floor(Math.random() * totalNoOfDocs);
        newarray.push(ops.splice(rnd,1)[0]);
        newarray.push(ops.splice(rnd,1)[0]);
    }

    for ( x = 1; x<=128; x*=2){
        res = benchRun( {
            parallel : x ,
            seconds : 5 ,
            ops : newarray
        } );
        print( "threads: " + x + "\t queries/sec: " + res.query );
    }
}