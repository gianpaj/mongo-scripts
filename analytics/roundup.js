
db = db.getSisterDB( "mongousage" )

// --- utils ----

function twoLetter(z){
    x = '' + z; 
    if ( x.length < 2 ) 
        return '0' + x; 
    return x; 
}

function getWeek(x){
    return x.week.year + '-' + twoLetter( x.week.month ) + '-' + twoLetter( x.week.day );
}

function getMonth(x){
    return x.date.year + '-' + twoLetter( x.date.month );
}

function firstPiece(x){
    if ( ! x )
        return "";
    var idx = x.indexOf( "/" );
    if ( idx == 0 ){
        x = x.substring(1);
        idx = x.indexOf( "/" );;
    }
    if ( idx < 0 ){
        return x;
    }
    return x.substring( 0 , idx );
}

function parseVersion( file ){
    if ( ! file )
        return null;
    
    if ( typeof ( myre ) == "undefined" ){
        myre = new RegExp( /(\d+\.\d+\.\d+)(.*)/ )
    }
    
    x = myre.exec( file )
    if ( ! x )
        return null;
    var v = x[1];
    if ( x[2].indexOf( "-rc" ) == 0 ){
        v += x[2].substring( 0 , x[2].indexOf( "." ) );
    }

    return v;
}

assert.eq( "foo" , firstPiece( "/foo/asd" ) )
assert.eq( "foo" , firstPiece( "foo/asd" ) )
assert.eq( "foo" , firstPiece( "/foo/" ) )

assert.eq( "05" , twoLetter( "5" ) , "test1a" )
assert.eq( "05" , twoLetter( "05" ) , "tes1b")

assert.eq( "1.4.4" , parseVersion( "/win32/mongodb-win32-i386-1.4.4.zip"  ) )
assert.eq( "1.4.4-rc2" , parseVersion( "/win32/mongodb-win32-i386-1.4.4-rc2.zip"  ) )

db.system.js.save( { _id : "twoLetter" , value : twoLetter } );
db.system.js.save( { _id : "getWeek" ,  value : getWeek }  );
db.system.js.save( { _id : "getMonth" , value : getMonth } );
db.system.js.save( { _id : "firstPiece" , value : firstPiece } );
db.system.js.save( { _id : "parseVersion" , value : parseVersion } );

db.downloads.ensureIndex( { day : 1 } )

// map/reduce helpers

simpleSum = function(k,values){ 
    return Array.sum( values ); 
}

assert.eq( 5 , simpleSum( "x" , [ 1 , 4 ] ) )

function downloadSummary(){

    // --- build ip tables ----

    m = function(){
        emit( { t : getMonth(this) , ip : this.ip } , 1 );
    }
    res = db.downloads.mapReduce( m , simpleSum , { out : "gen.monthly.ip" } )

    m = function(){
        emit( { t : getWeek(this) , ip : this.ip } , 1 );
    }
    res = db.downloads.mapReduce( m , simpleSum , { out : "gen.weekly.ip" } )

    // ---- do rollups for downloads

    rollup = function(key,values){
        var res = { total : 0 , unique : 0 };
        for ( var i=0; i<values.length; i++ ){
            res.total += values[i].total;
            res.unique += values[i].unique;
        }
        return res;
    }

    m = function(){
        emit( this._id.t , { total : this.value , unique : 1 } )
    }
    res = db.gen.monthly.ip.mapReduce( m , rollup , { out : "gen.monthly" } )
    res.find().sort( { _id : -1 } ).forEach( printjsononeline )

    res = db.gen.weekly.ip.mapReduce( m , rollup , { out : "gen.weekly" } )
    res.find().sort( { _id : -1 } ).forEach( printjsononeline )

}


// top domains
function doDomains( numDays ){
    var since = new Date( new Date().getTime() - ( 86400 * 1000 * numDays ) )

    var q = 
        { 
            reverseDomain : { $exists : true } ,
            day : { $gt : since } 
        }
    
    print( "top domains since: " + since + " \t" + db.downloads.find( q ).count() +  " / " + db.downloads.find( { day : { $gt : since } } ).count() )

    var coll = "gen.domains.day" + numDays;
    db.downloads.mapReduce( function(){ emit( this.reverseDomain , 1 ); } ,
                            simpleSum , 
                            { out : coll , query : q } );
    db[coll].ensureIndex( { value : 1 } )
}

// top files 
function topFiles( numDays ){
    var since = new Date( new Date().getTime() - ( 86400 * 1000 * numDays ) )
    print( "topFiles since: " + since )
    
    var q = { day : { $gt : since } }

    var coll = "gen.files.day" + numDays;
    db.downloads.mapReduce( function(){ emit( this["uri-stem"] , 1 ); } ,
                            simpleSum , 
                            { out : coll , query : q } );
    db[coll].ensureIndex( { value : 1 } )
}


function topPieces( numDays ){
    var since = new Date( new Date().getTime() - ( 86400 * 1000 * numDays ) )
    print( "topPieces since: " + since )

    var q = { day : { $gt : since } }

    var coll = "gen.firstPiece.day" + numDays;
    db.downloads.mapReduce( function(){ emit( firstPiece( this["uri-stem"] ) , 1 ); } ,
                            simpleSum ,
                            { out : coll , query : q } );
    db[coll].ensureIndex( { value : 1 } )
}




function doGroups( numDays ){
    doDomains( numDays )
    topFiles( numDays )
    topPieces( numDays );
}

function doVersions(){
    res = db.downloads.mapReduce( 
        function(){ 
            v = parseVersion( this["uri-stem"] );
            if ( v )
                emit( v , 1 );
        } , simpleSum , { out : "gen.versions" } );
    res.find().sort( { _id : -1 } ).forEach( printjson );
        
}

downloadSummary();
doGroups( 7 )
doGroups( 15 )
doGroups( 30 )

doVersions()
