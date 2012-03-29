
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
    case 6: return "Closed";
    case 10006: return "Waiting for Customer"
    case 10007: return "Waiting for bug fix"
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

    for ( var key in data ) {
        var match = null;
        for ( var i=0; i<nodes.length; i++ ) {
            if ( nodes[i].key != key )
                continue;
            match = nodes[i];
            break;
        }
        
        if ( ! match ) {
            console.log( "no match for: " + key );
            continue;
        }

        var small = match.large.find( "span.y2" );
        
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

function findAllJiraThings() {
    var all = []
    
    var r = /.MongoDB-JIRA. +\(([A-Z]+\-\d+)\)/;

    $( "#canvas_frame" ).contents().find( "div.av" ).each(
        function(index) {
            if ( $(this).html() != "mongo-jira" )
                return;
            
            var x = $(this);
            
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
            
            all.push( { label : $(this) , large : x , key : res[1] } )

        }
    );
    
    return all;
}

var doWork = function() {

    // You can probably combine the document scan for read and unread into one find.

    var srch = "[mongodb-user]";
    var srchIndex = document.title.indexOf( srch );

    if ( document.title.indexOf( "Inbox" ) >= 0 ) {
        setMyHTML( "" );
        
        var nodes = findAllJiraThings();
        
        var url = "https://corp.10gen.com/jiramulti?issues=";        

        for ( var i=0; i<nodes.length; i++ ) {
            url += nodes[i].key + ","
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

var highlight = setInterval( doWork , 5000 );
