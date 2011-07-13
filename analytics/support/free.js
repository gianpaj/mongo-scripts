
db = db.getSisterDB( "support_gg" )

goodmail = {}
db.users.find().forEach( 
    function(z){
        for ( var i=0; i<z.mail.length; i++ ) {
            goodmail[z.mail[i]] = true;
        }
    }
);

function doTimePeriod( start , end ) { 
    var options = { out : { inline : true } , query : {} };
    
    var scope = { start : start , end : end };
    options.scope = scope;
    
    var res = db.topics.mapReduce(
        function(){
            
            var seen = {}
            var good = false;

            for ( var i=0; i<this.messages.length; i++ ) {
                var from = this.messages[i].from;
                if ( start && this.messages[i].date < start )
                    continue;
                if ( end && this.messages[i].date > end )
                    continue;

                good = true;
                
                if ( from.indexOf( "<" ) >= 0 ) {
                    from = from.substring( from.indexOf( "<" ) + 1 );
                    from = from.substring( 0 , from.indexOf( ">" ) );
                }
                emit( from , { topics : 0 , messages : 1 } );
                if ( ! seen[from] ) {
                    seen[from] = true;
                    emit( from , { topics : 1 , messages : 0 } );
                }
                
            }
            
            if ( good ) 
                emit( "TOTAL@10gen.com" , { topics : 1 , messages : 1 } )
            
        } ,
        function(k,vs){
            var total = { topics : 0 , messages : 0 };
            for ( var i=0; i<vs.length; i++ ) {
                total.topics += vs[i].topics;
                total.messages += vs[i].messages;
            }
            return total;
        } , 
        options );        
    
    res = res.results.filter( 
        function(z){
            var e = z._id;
            if ( e.indexOf( "@10gen.com" ) > 0 )
                return true;
            if ( e.indexOf( "nat.lueng@gmail.com" ) == 0 )
                return true;
            return goodmail[e];
        }
    );


    
    res = res.sort( function(a,b){ return b.value.messages - a.value.messages; } )
    
    var total = 0;

    print( "from " + start + " to " + end );
    for ( var i=0; i<res.length; i++ ) {
        print( "\t\t" + res[i]._id + "\t\t" + res[i].value.messages )
        total += res[i].value;
    }
    
    var temp = 0;
    for ( var i=0; i<res.length; i++ ){
        temp += Math.pow( res[i].value - ( total / res.length ) , 2 );
    }

}


for ( var startMonth=3; startMonth<6; startMonth++ ) {
    doTimePeriod( new Date( 2011 , startMonth , 1 , 0 , 0 ) , new Date( 2011 , startMonth + 1 , 0 , 23 , 59, 59 ) )
}
