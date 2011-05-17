import urllib2
import re
import datetime
import time
import pymongo
import BeautifulSoup

def get_value( tag , a ):
    for x in tag.attrs:
        if x[0] == a:
            return x[1]
    return None


class GoogleGroup:
    def __init__(self,name):
        self.name = name
        self.cache = pymongo.Connection().gg_cache.cache
        self.opener = urllib2.build_opener()  

        self._debug = False
        self.use_cache_timeout = True

        if self._debug:
            self.use_cache_timeout = False
        
    def debug(self,msg):
        if self._debug:
            print( msg )

    def fetch(self,path,timeout_minutes=1):
        q = { "_id" : path }
        if self.use_cache_timeout:
            q["ts"] = { "$gt" : time.time() - ( timeout_minutes * 60 ) }
        
        x = self.cache.find_one( q )
        if x:
            return x["data"]
        
        fullpath = "http://groups.google.com" + path 

        def do_fetch():
            request = urllib2.Request( fullpath )
            request.add_header('User-Agent','Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_4; en-US) AppleWebKit/533.4 (KHTML, like Gecko) Chrome/5.0.375.125 Safari/533.4') 
        
            return self.opener.open( request ).read()

        try:
            data = do_fetch()
        except urllib2.HTTPError,e:
            print( "couldn't download %s because of %s" % ( fullpath , str(e) ) )
            time.sleep( 5 )
            data = do_fetch()

        self.cache.save( { "_id" : path , "data" : data , "ts" : time.time() } )
        return data


    def clean_link(self,link):
        if link.find( "browse_thread/thread" ) < 0:
            return None
        
        a,b,c = link.partition( "/thread/" )
        for p in [ "/" , "?" , "#" , "<" , ">" , "\"" , "'" ]:
            c = c.partition( p )[0]
            
        fixed = a + b + c 

        if len(fixed) != 57:
            self.debug( "bad length [%s] %d" % ( fixed , len(fixed) ) )
            return None


        return fixed

    def extrackThreadLinks(self,page):
        links = set()
        for x in re.findall( "((/group/mongodb-user/browse_thread/thread/(.*?))[/\#\"&])" , page):
            z = self.clean_link( x[1] )
            if z:
                links.add(z)
        return links

    def getThreads(self,pages_back=1):
        seen = set()
        
        path = "/group/%s/topics" % self.name

        for i in range(pages_back):
            p = path + "?gvc=2&tsc=1&"
            if len(seen) > 0:
                p += "start=" + str(1 + len(seen) )
            self.debug( p )

            page = self.fetch( p )
            
            thisTime = self.extrackThreadLinks( page )
            seen.update( thisTime )

            self.debug( "unique thisTime: %d total unique: %d " % ( len(thisTime) , len(seen) ) )

        if False and pages_back == 1:
            # this is a dirty dirty hack
            for x in self.cache.find():
                if x["_id"].find( "/browse_thread/" ) >= 0:
                    seen.add( x["_id"] )
                seen.update( self.extrackThreadLinks( x["data"] ) )
            
        return seen


    def getThreadDetail(self,path,other_links=None):
        self.debug( path )
        page = self.fetch( path , timeout_minutes=120 )

        soup = BeautifulSoup.BeautifulStoneSoup( page , convertEntities=BeautifulSoup.BeautifulStoneSoup.XML_ENTITIES )
        
        subject = ""

        nodes = soup.find( id="thread_subject_site" )
        if nodes is None or len(nodes) == 0:
            raise Exception( "no title on: %s" % path )
        
        for x in nodes:
            subject += str(x)
        subject = subject.strip()
        
        messages = []
        for a in soup.findAll( id="hdn_author" ):
            d = a.parent.find( id="hdn_date" )

            a = get_value( a , "value" )
            d = get_value( d , "value" )
            d = d.replace( "&nbsp;" , " " )

            try:
                d = datetime.datetime.strptime( d , "%b %d, %I:%M %p" )
            except:
                d = datetime.datetime.strptime( d , "%b %d %Y, %I:%M %p" )
            
            y = d.year
            if y == 1900:
                y = datetime.datetime.now().year
                
            d = datetime.datetime( year=y, month=d.month, day=d.day, hour=d.hour,minute=d.minute )
            messages.append( { "date" : d , "from":  a } )
            
        if other_links is not None:
            other_links.update( self.extrackThreadLinks(page) )

        return { "subject" : subject , "messages" : messages }
        
