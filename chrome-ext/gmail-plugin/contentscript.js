
crap = 1

rsplitOn = function( str , what ) { 
    var idx = str.lastIndexOf( what );
    if ( idx < 0 )
        return str;
    
    return str.substring( 0 , idx );
}

var lastHTML = "";

function setMyHTML( html ) {
    if ( html == lastHTML )
        return;
    lastHTML = html
    var found = false;
    $( '#canvas_frame' ).contents().find( '#xgenhack1' ).each(
        function() {
            found = true;
            $(this).html( html );
        }
    );

    if ( found ) 
        return;

    console.log( "not found addding" );  

    var last = null;

    $( '#canvas_frame' ).contents().find( '.oy8Mbf' ).each( 
        function(z){
            last = $(this);
        }
    );
    last.append( "<div id='xgenhack1'>" + html + "</div>" );

}

var lastMultiUrl = null;

function displayStatus( s ) {
    s = parseInt( s );
    
    switch ( s ) {
    case 1: return "Open";
    case 3: return "In Progress";
    case 4: return "Reopened";
    case 5: return "<span style='color:purple;'>Resolved</span>";
    case 6: return "<span style='color:purple;'>Closed</span>";
    case 10006: return "<span style='color:pink;'>waiting for customer</span>";
    case 10007: return "<span style='color:pink;'>waiting for bug fix</span>";
    }

    return s;
}

function displayPriority( p ) {
    p = parseInt( p );
    var imgName = null;
    if ( p == 1 )
        imgName = "blocker";
    else if ( p == 2 )
        imgName = "critical";

    if ( imgName )
        return "<img src='https://jira.mongodb.org/images/icons/priority_" + imgName + ".gif'/>";

    return "P" + p;
}

jiraData = null;

function jiraMultiCallback( data ) {
    jiraData = data

    console.log( data );
    
    var nodes = findAllJiraThings();
    console.log( "number of nodes: " + nodes.length )
    for ( var key in data ) {
        var match = null;
        for ( var i=0; i<nodes.length; i++ ) {
            if ( nodes[i].key != key )
                continue;
            match = nodes[i];
            console.log( "got a match [" + nodes[i].key + "] [" + key + "]" + data[key] )
            break;
        }
        
        if ( ! match ) {
            console.log( "no match for: " + key );
            continue;
        }
        
        var small = match.large.find( "span.y2" );
        console.log( match.large )
        
        var issue = data[key];

        var newhtml = "&nbsp;<b>";
        if ( issue["error"] )
            newhtml += issue["error"]

        newhtml += displayStatus( issue["status"] ) + "&nbsp;";
        newhtml += displayPriority( issue["priority"] ) + "&nbsp;";

        if ( issue["assignee"] ) 
            newhtml += issue["assignee"] + "&nbsp;";
        
        if ( issue["fixVersions"] && issue["fixVersions"].length )
            newhtml += issue["fixVersions"]

        if ( issue["customer"] && issue["customer"].length )
            newhtml += issue["customer"]

        
        newhtml += "</b>";

        small.html( newhtml );
    }
}

/**
* @return [ { label : <the actual label node> , large : <node holding whole row> , key : <identifier> } ]
*/
function findAllJiraThings() {
    var all = []
    
    var config = [ 
        { r : /.MongoDB-JIRA. +\(([A-Z]+\-\d+)\)/ , l : "mongo-jira" } ,
        { r : /(.mongodb-user. [\d\w\-\' \?\.:\(\)]+)/ , l : "google group" } 
    ];
    
    $( "#\\:rp" ).find( "div.av" ).each(
        function(index) {
            
            var x = null;
            var r = null;
            for ( var i=0; i<config.length; i++ ) {
                if ( $(this).html() == config[i].l ) {
                    x = $(this);
                    r = config[i].r;
                }
            }

            if ( ! x ) 
                return;
            
            var res = null;
            for ( var j=0; j<12; j++ ) {
                x = x.parent();
                var html = x.html();
                res = r.exec( html );
                if ( res )
                    break;
            }
            
            if ( ! res )
                return;
            
            var doc = { label : $(this) , large : x , key : res[1] };
            all.push( doc );
        }
    );


    
    return all;
}

var doWork = function() {

    // You can probably combine the document scan for read and unread into one find.

    var srch = "[mongodb-user]";
    var srchIndex = document.title.indexOf( srch );

    console.log( "title: " + document.title )
    if ( document.title.indexOf( "Inbox" ) >= 0 ) {
        setMyHTML( "" );
        
        var nodes = findAllJiraThings();
        
        var url = "https://corp.10gen.com/jiramulti?issues=";        

        for ( var i=0; i<nodes.length; i++ ) {
            url += escape( nodes[i].key ) + ","
        }
        
        url += "&t=" + Math.floor( (new Date()).getTime() / 300000 );
        
        if ( ! jiraData || lastMultiUrl != url ) {
            console.log( url )
            lastMultiUrl = url;
            $.getJSON( url  , jiraMultiCallback );
        }
        else {
            jiraMultiCallback( jiraData );
        }

    }
    else if ( srchIndex >= 0 ) {
        var subject = document.title.substring( srchIndex + srch.length );
        subject = rsplitOn( subject , "@" );
        subject = rsplitOn( subject , "-" );
        subject = subject.trim();
        
        setMyHTML("<iframe width='600' height='70' src='https://corp.10gen.com/gggiframe?subject=" + escape( subject ) + "'></iframe>" )
    }
    else {
        setMyHTML( "" );
    }

}

var highlight = setInterval( doWork , 30 * 1000 );
