

urls = Array();
urls.push( { url : "https://monitor.foursquare.com/ganglia/graph.php?g=checkins_report&z=large&c=checkins&h=checkins-backup-1&m=load_one&r=week&s=descending&hc=4&mc=2&st=1287094450" , title : "foursquare data size" } );
urls.push( { url : "http://search.twitter.com/search?q=mongodb" , title : "twiter" } );

countdownStart = 120;
countdown = 0;
pos = 0;

function skip(){
    countdown = 1;
}

function go(){
    if ( countdown <= 0 ){
        if ( pos >= urls.length) pos = 0;
        var u = urls[pos++]
        document.getElementById( "myFrame" ).src = u.url + "&foorand=" + Math.random();
        document.getElementById( "myTitle" ).innerHTML = u.title;
        countdown = countdownStart;
        document.getElementById( "clock" ).style.background = "red";
    }
    
    countdown--;
    document.getElementById( "clock" ).innerHTML = countdown;
    setTimeout( go , 1000 );
}

function resetMessage(){
    document.getElementById( "clock" ).style.background = "white";
}

setTimeout( go , 1000 );

