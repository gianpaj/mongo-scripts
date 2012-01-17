// Page.java

package com.tengen.http;

import java.io.*;
import java.net.*;
import java.util.*;

public class Page {
    
    Page( String url , String data , Map<String,List<String>> headers ) {
        _url = url;
        _data = data;
        _headers = headers;
    }

    public String getURL() { return _url; }
    public String getData() { return _data; }
    public Map<String,List<String>> getHeaders() { return _headers; }

    final String _url;
    final String _data;
    final Map<String,List<String>> _headers;

    public static Page download( String url ) 
        throws IOException {
        
        URL u = new URL( url );
        HttpURLConnection conn = (HttpURLConnection)u.openConnection();

        conn.connect();
        
        String data = readFully( conn.getInputStream() );
        
        return new Page( url , data, conn.getHeaderFields() );
    }

    // --------

    public static String readFully(InputStream is) 
        throws IOException {
        return readFully(new InputStreamReader(is));
    }
    
    public static String readFully(InputStreamReader isr) 
        throws IOException {
        return readFully(new BufferedReader(isr));
    }
    
    public static String readFully(BufferedReader br) 
        throws IOException {
        StringBuilder buf = new StringBuilder();
        String line;
        while ((line = br.readLine()) != null) {
            buf.append(line);
            buf.append('\n');
        }
        return buf.toString();
    }    


    // ----

    public static void main( String[] args )
        throws Exception {
        
        String url = "http://www.google.com/";
        if ( args.length > 0 )
            url = args[0];
        
        Page p = download( url );
        System.out.println( p.getData() );
        
    }
        
}
