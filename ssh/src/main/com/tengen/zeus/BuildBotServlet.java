// BuildBotServlet.java

package com.tengen.zeus;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.logging.*;
import java.util.regex.*;

import javax.servlet.*;
import javax.servlet.http.*;

import com.tengen.http.*;

public class BuildBotServlet extends HttpServlet {

    public BuildBotServlet() {
        _bbs.put( "main" , new BuildBot( "http://buildbot.mongodb.org:8081/" ) );
    }
    
    public void doGet(HttpServletRequest req,HttpServletResponse res ) 
        throws ServletException , IOException {
        
        
        String path = req.getServletPath();
        
        int idx = path.indexOf( "/f/" );
        if ( idx < 0 )
            return;
        
        path = path.substring( idx + 3 );
        
        idx = path.indexOf( "/" );
        if ( idx < 0 )
            return;

        String name = path.substring( 0 , idx );
        String filter = path.substring( idx + 1 );
        
        BuildBot bb = _bbs.get( name );
        if ( bb == null ) {
            PrintWriter out= res.getWriter();
            out.println("No bb for [" + name + "]" );
            return;
        }

        Set<String> builders = bb.getBuilders( filter );
        res.sendRedirect( bb.waterfallForBuilders( builders ) );
    }

    
    final Map<String,BuildBot> _bbs = new TreeMap<String,BuildBot>();
}
