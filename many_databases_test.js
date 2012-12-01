var numDbs = 2000;
var numOps = 100;
var numDocs = 10000;
var numCols = 10;

// 100 = 10000 / 100
var numDocsPerColl = numDocs / numDbs / numCols;

var complexDoc = {'product_name': 'Soap', 'weight': 22, 'weight_unit': 'kilogram', 'unique_url': 'http://amazon.com/soap22', 'categories': [{'title': 'cleaning', 'order': 29}, {'title': 'pets', 'order': 19}], 'reviews': [{'author': 'Whisper Jack','message': 'my dog is still dirty, but i`m clean'}, {'author': 'Happy Marry','message': 'my cat is never been this clean'}]};

var ops = [];

// Create databases, insert one document
// and prepare 2 operations to benchmark on that last document
for ( i = 0; i < numDbs; i++ ) {
    var find_op =  {
        "op" : "findOne"
    };

    var update_op = {
        "op" : "update",
        "update" : { "$inc" : { "weight" : 1 } }
    };
    var db = db.getSisterDB('boom-' + i);
    // drop every database 'boom-*'
    db.dropDatabase();

    for (var y = 0; y < numCols; y++) {
        
        coll = db['boom-'+ y];

        find_op.ns = coll.toString();
        update_op.ns = coll.toString();

        // this should loop 2000000 times
        for (var j = 0; j < numDocsPerColl; j++) {
            // insert docs in each db
            complexDoc._id = new ObjectId();
            coll.insert(complexDoc);
            var query = { "_id" : complexDoc._id };
            find_op.query = query;
            ops.push(find_op);
            update_op.query = query;
            ops.push(update_op);
        }
    }
}
var original_ops = ops;

// actual benchmark function
function benchmark () {
    // start from the original operations array and find other x (numOps) no. random of ops
    ops = original_ops.slice(0);

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
            ops : ops
        } );
        print( "threads: " + x + "\t queries/sec: " + res.query );
    }
}