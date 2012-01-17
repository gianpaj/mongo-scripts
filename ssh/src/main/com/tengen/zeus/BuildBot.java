// BuildBot.java

package com.tengen.zeus;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.logging.*;
import java.util.regex.*;

import com.tengen.http.*;

public class BuildBot {
    
    static Pattern BUILDER_REGEX = Pattern.compile( "href=\"builders/(.*?)\"" );
    static Logger LOGGER = Logger.getLogger( "xgen.zeus.buildbot" );
    
    public BuildBot( String root ) {
        
        if ( ! root.endsWith( "/" ) )
            root += "/";
        _root = root;

        LOGGER.info( "created: " + _root );
    }

    public Set<String> getBuilders( String filter ) 
        throws IOException {
        
        filter = filter.toLowerCase();

        Set<String> fixed = new TreeSet<String>();
        
        for ( String b : getBuilders() )
            if ( b.toLowerCase().indexOf( filter ) >= 0 )
                fixed.add( b );

        return fixed;
    }
    
    public Set<String> getBuilders() 
        throws IOException {
        
        if ( _builders != null && ( System.currentTimeMillis() - _lastFetchTime ) < 600 ) {
            LOGGER.fine( "cached" );
            return _builders;
        }

        Page page = Page.download( _root + "builders" );
        LOGGER.fine( "fetched" );
        Set<String> builders = new TreeSet<String>();
        
        Matcher m = BUILDER_REGEX.matcher( page.getData() );
        while ( m.find() ) {
            
            String name = m.group(1);
            if ( name.indexOf( "/" ) > 0 )
                name = name.substring( 0 , name.indexOf( "/" ) );
            
            name = URLDecoder.decode( name , "UTF-8" );
            
            builders.add( name );
        }
        
        _builders = builders;
        _lastFetchTime = System.currentTimeMillis();
        return _builders;
    }
    
    
    public String waterfallForBuilders( Collection<String> builders ) {
        StringBuilder buf = new StringBuilder();
        buf.append( _root );
        buf.append( "waterfall?reload=60" );
        
        try {
            for ( String b : builders )
                buf.append( "&builder=" ).append( URLEncoder.encode( b , "UTF-8" ) );
        }
        catch ( UnsupportedEncodingException u ) {
            throw new RuntimeException( "wtf?" , u );
        }
        
        return buf.toString();
    }

    final String _root;
    
    private long _lastFetchTime = 0;
    private Set<String> _builders;

    public static void main( String[] args )
        throws Exception {
        
        BuildBot bb = new BuildBot( "http://buildbot.mongodb.org:8081/" );
        Set<String> builders = bb.getBuilders("V2.0");
        System.out.println( builders );
        System.out.println( bb.waterfallForBuilders( builders ) );
        bb.getBuilders();
        bb.getBuilders();
    }

}
