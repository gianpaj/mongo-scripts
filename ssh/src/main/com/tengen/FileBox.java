// FileBox.java

package com.tengen;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.regex.*;
import java.util.concurrent.atomic.*;

import org.apache.sshd.*;
import org.apache.sshd.server.*;
import org.apache.sshd.common.*;
import org.apache.sshd.server.keyprovider.*;
import org.apache.sshd.server.shell.*;
import org.apache.sshd.server.command.*;
import org.apache.sshd.server.session.*;

import com.tengen.ssh.*;

public class FileBox extends SSHBase {
    public boolean authenticate(String username, String password, ServerSession session){
        return true;
    }

    public Command createCommand( String s ){
        String pcs[] = Pattern.compile( "\\s+" ).split(s);
        if ( pcs[0].equals( "scp" ) )
            return new IncomingSCP( pcs , true );
        throw new RuntimeException( "unknown command [" + s + "]" );
    }


    public static void main( String args[] )
        throws Exception {
        FileBox fb = new FileBox();
        fb.run();
    }

}
