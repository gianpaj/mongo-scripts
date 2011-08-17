
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

var doWork = function() {

    // You can probably combine the document scan for read and unread into one find.

    /*
    // This is for read email.
    $('#canvas_frame').contents().find('span.yP').each(function(index) {
        if ($(this).attr('email') != 'dan@10gen.com') return;
        $(this).css('color', '#FF0000');
    });

    // This is for unread email.
    $('#canvas_frame').contents().find('span.zF').each(function(index) {
        if ($(this).attr('email') != 'dan@10gen.com') return;
        $(this).css('color', '#FF0000');
    });
*/

    var srch = "[mongodb-user]";

    var idx = document.title.indexOf( srch );
    if ( idx < 0 ) {
        setMyHTML( "" );
        return;
    }
    
    var subject = document.title.substring( idx + srch.length );
    subject = rsplitOn( subject , "@" );
    subject = rsplitOn( subject , "-" );
    subject = subject.trim();

    
    setMyHTML("<iframe width='600' height='70' src='https://corp.10gen.com/gggiframe?subject=" + escape( subject ) + "'></iframe>" )
}

var highlight = setInterval( doWork , 5000 );
