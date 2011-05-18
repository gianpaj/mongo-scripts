
import pymongo
import datetime

conn = pymongo.Connection( "mmsdb1b.10gen.cc:27018"  )
db = conn.mmsdb

## versions

#    major only
v = db.config.hosts.inline_map_reduce( "function(){ var v = this.v; if ( ! v ) return; var i=v.indexOf( '.' ); i = v.indexOf( '.' , i + 1 ); emit( v.substring(0,i) , 1 ); }" , 
                                       "function(k,v){ return Array.sum(v); }" )

v.sort( lambda a,b: int(b["value"] - a["value"]) )

print( "instances by major version" )
for x in v:
    print( "%-17s\t%s" % ( x["_id"] , x["value"] ) )

print( "\n\n" )

#   detailed

since = datetime.datetime.now()
since = since - datetime.timedelta( weeks=1 )

v = db.config.hosts.group( { "v" : 1 } , { "l" : { "$gt" : since } } ,
                           { "count" : 1 }, "function(v,p){ p.count++; }" )
v.sort( lambda a,b: int(b["count"] - a["count"]) )

print( "instances by version" )
for x in v:
    if not x["v"]:
        continue
    print( "%-17s\t%s" % ( x["v"] , x["count"] ) )



