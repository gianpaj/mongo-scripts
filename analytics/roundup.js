
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

assert.eq( "05" , twoLetter( "5" ) , "test1a" )
assert.eq( "05" , twoLetter( "05" ) , "tes1b")

db.system.js.update( { _id : "twoLetter" } , { value : twoLetter } , true );
db.system.js.update( { _id : "getWeek" } , { value : getWeek } , true );
db.system.js.update( { _id : "getMonth" } , { value : getMonth } , true );

db.downloads.ensureIndex( { day : 1 } )

// map/reduce helpers

simpleSum = function(k,values){ 
    return Array.sum( values ); 
}


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
    
    print( "since: " + since + " \t" + db.downloads.find( q ).count() +  " / " + db.downloads.find( { day : { $gt : since } } ).count() )

    var coll = "gen.domains.day" + numDays;
    db.downloads.mapReduce( function(){ emit( this.reverseDomain , 1 ); } ,
                            simpleSum , 
                            { out : coll , query : q } );
    db[coll].ensureIndex( { value : 1 } )
}




downloadSummary();
doDomains( 7 )
doDomains( 15 )
doDomains( 30 )

