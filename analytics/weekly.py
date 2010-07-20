
import sys
import socket
from time import strptime , strftime
import re

import simples3
import settings # for s3

import smtplib
from email.MIMEText import MIMEText

import _mysql
import memcache

db=_mysql.connect( user=settings.dbuser , passwd=settings.dbpass , db="mongousage")
mc = memcache.Client( [ "127.0.0.1:11211" ] )

def addGZ( n ):
    return [ n , n + ".gz" ]

badEndings = []
for x in [ "Packages" , "Packages.bz2" , "Release" , "Sources" , 
           ".xml" , ".dsc" , ".md5" , ".gpg" 
           , ".pdf" , ".html" , ".png" , ".conf" ]:
    badEndings.append( x )
    badEndings.append( x + ".gz" )

badStrings = [ "misc/boost" ]

goodEndings = [ ".tar.gz" , ".tgz" , ".zip" , ".deb" , ".rpm" ]


# -1 bad, 0 unknown 1 good
def decide( key ):
    for e in badEndings:
        if key.endswith( e ):
            return -1
    for e in badStrings:
        if key.find( e ) >= 0:
            return -1
    for e in goodEndings:
        if key.endswith( e ):
            return 1
    return 0

def updateData( debug=False ):

    s3_line_logpats  = r'(\S+) (\S+) \[(.*?)\] (\S+) (\S+) ' \
        r'(\S+) (\S+) (\S+) "([^"]+)" ' \
        r'(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) ' \
        r'"([^"]+)" "([^"]+)"'

    s3_line_logpat = re.compile(s3_line_logpats)

    (S3_LOG_BUCKET_OWNER, S3_LOG_BUCKET, S3_LOG_DATETIME, S3_LOG_IP,
     S3_LOG_REQUESTOR_ID, S3_LOG_REQUEST_ID, S3_LOG_OPERATION, S3_LOG_KEY,
     S3_LOG_HTTP_METHOD_URI_PROTO, S3_LOG_HTTP_STATUS, S3_LOG_S3_ERROR,
     S3_LOG_BYTES_SENT, S3_LOG_OBJECT_SIZE, S3_LOG_TOTAL_TIME,
     S3_LOG_TURN_AROUND_TIME, S3_LOG_REFERER, S3_LOG_USER_AGENT) = range(17)

    s3_names = ("bucket_owner", "bucket", "datetime", "ip", "requestor_id", 
                "request_id", "operation", "key", "http_method_uri_proto", "http_status", 
                "s3_error", "bytes_sent", "object_size", "total_time", "turn_around_time",
                "referer", "user_agent")

    def parse_s3_log_line(line):
        match = s3_line_logpat.match(line)
        result = [match.group(1+n) for n in range(17)]
        return result

    def parseLine( line ):
        d = {}
        for ( name , val ) in zip( s3_names , parse_s3_log_line( line ) ):
            d[ name ] = val
        return d


    db.query( "create table if not exists downloads( day date , ip varchar(64) , os varchar(12) , file varchar(256) , log_line text )" )

    s = simples3.S3Bucket( settings.bucket , settings.id , settings.key )
    seen = 0

    def fetch( key ):
        mckey = "s3log-" + key
        raw = mc.get( mckey )
        if not raw:
            raw = s.get( key ).read()
            mc.set( mckey , raw )
        return raw.splitlines()

    def go( filter ):
        for (key, modify, etag, size) in s.listdir(prefix=filter):
            print( "\t" + key )
            for line in fetch( key ):
                #print( "\t\t" + line )

                try:
                    data = parseLine( line )
                except:
                    continue

                key = data["key"]
                ts = strptime( data["datetime"] , "%d/%b/%Y:%H:%M:%S +0000" )

                if data["ip"] == "64.70.120.90":
                    continue

                if data["user_agent"].find( "bot" ) >= 0:
                    if debug:
                        print( "BOT: " + line )
                    continue

                if line.find( " 200 " ) < 0:
                    continue
                
                if key == "-" or key.startswith( "log/" ):
                    continue


                res = decide(key)
                if res == 1:
                    db.query( "INSERT INTO downloads VALUES( '%s' , '%s' , '%s' , '%s' , '%s' )" %
                              ( strftime( "%Y-%m-%d" , ts ) , data["ip"] , key.partition( "/" )[0] , key , line ) )
                elif res == 0:
                    print( "skipping unknown: " + key )

    def dayHash( y , m , d ):
        return ( int( y ) * 10000 ) + ( int( m ) * 100 ) + int( d )

    db.query( "select year( max(day) ) , month( max(day) ) , day( max( day ) ) , max( day ) from downloads" );
    lastDay = db.store_result().fetch_row()[0]
    lastDayHash = dayHash( lastDay[0] , lastDay[1] , lastDay[2] )

    db.query( "select year( now() ) , month( now() ) , day( now() ) , max( day ) from downloads" );
    curDay = db.store_result().fetch_row()[0]
    curDayHash = dayHash( curDay[0] , curDay[1] , curDay[2] )

    db.query( "delete from downloads where day = \"%s\" " % lastDay[3] )

    for y in [ 2009 , 2010 ]:
        for m in range( 12 ):
            for d in range( 31 ):
                day = "log/access_log-%d-%02d-%02d" % ( y , m + 1 , d + 1 )
                if dayHash( y , m + 1 , d + 1 ) < lastDayHash:
                    continue
                if dayHash( y , m + 1 , d + 1 ) > curDayHash:
                    continue
                print( day + ":" + str( dayHash( y , m + 1 , d + 1 ) ) );
                go( day )


def sendMail( debug=False ):
    
    body = "Weekly\n"

    def dump( q ):
        txt = ""
        db.query( q )
        res = db.store_result()
        while True:
            row = res.fetch_row()
            if not row:
                break
            row = row[0]
            txt += str( row[0] ) + "\t" + str( row[1] ) + "\n"
        return txt


    body += dump( "select min(day) week , count(distinct(ip)) unique_ips from downloads where yearweek(day) < yearweek(current_date) group by yearweek(day)" )

    body += "\n\nMontly\n"
    body += dump( "select min(day) month , count(distinct(ip)) unique_ips from downloads group by year(day) , month(day)" )

    body += "\n\nLast Week by OS\n"
    body += dump( "select os , count(distinct(ip)) unique_ips from downloads where yearweek(day) = yearweek( current_date - interval 1 week) and os != 'log' and os != 'stats' group by os order by unique_ips DESC  " )

    body += "\n\n--- total non-unique ---\n\n"
    
    body += "weekly\n";
    body += dump( "select min(day) week , count(*) unique_ips from downloads where yearweek(day) < yearweek(current_date) group by yearweek(day) " )

    body += "\n\nMontly\n"
    body += dump( "select min(day) month , count(*) unique_ips from downloads group by year(day) , month(day)" )

    if False:
        body += "\n\nReverse ips from last week\n"

        db.query( "create table if not exists ips( ip varchar(64) primary key , name varchar(256) )" )

        def byip_net( ip ):
            try:
                info = str( socket.gethostbyaddr( ip ) )
                return info[2]
            except:
                return ""

        def byip_db( ip ):
            db.query( "select name from ips where ip=\"%s\"" % ip )
            temp = db.store_result().fetch_row()
            if not temp:
                return None
            return temp[0][0]

        def byip( ip ):
            host = byip_db( ip )
            if host is not None:
                print( "cached" )
                return host
            host = byip_net( ip );
            db.query( "insert into ips( ip , name ) VALUES ( \"%s\" , \"%s\" )" % ( ip , host ) )
            return host

        def shouldDisplay( host ):
            if host is None or host == "":
                return False
            return True

        db.query( "select distinct(ip) from downloads where yearweek(day) = yearweek(current_date - interval 1 week) limit 10" )
        res = db.store_result()
        while True:
            row = res.fetch_row()
            if not row:
                break
            row = row[0][0]
            row = byip( row )
            if shouldDisplay( row ):
                body += row + "\n"


    print body

    if not debug:
        to = [ "everyone@10gen.com" , "board@10gen.com" ]
        msg = MIMEText(body)
        msg['Subject'] = "Mongo Download Usage"
        msg['From']    = "eliot@10gen.com"
        msg['To']      = ",".join(to)
        s = smtplib.SMTP( "ASPMX.L.GOOGLE.com" )
        #s.set_debuglevel(True)
        s.sendmail( "eliot@10gen.com", to , msg.as_string() )
        print s.quit()

if __name__ == "__main__":
    if len( sys.argv ) > 1:
        sendMail( False )
    else:
        try:
            updateData()
        except:
            print "error getting data, trying again..."
            updateData()
        sendMail()
