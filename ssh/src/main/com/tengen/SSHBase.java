// SSHBase.java

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

public abstract class SSHBase implements PasswordAuthenticator , CommandFactory , 
                                         Factory<Command> , TcpIpForwardFilter {
    
    public SSHBase(){
        this( 9999 );
    }

    public SSHBase( int port ){
        _server = SshServer.setUpDefaultServer();
        _server.setPort( port );

        _server.setKeyPairProvider( new SimpleGeneratorHostKeyProvider("hostkey.ser") );
        _server.setShellFactory( this );
        _server.setCommandFactory( this );
        _server.setPasswordAuthenticator( this );
        _server.setTcpIpForwardFilter( this );
    }

    public Command create(){
        throw new RuntimeException( "shell not allowed" );
    }

    public Command createCommand( String s ){
        throw new RuntimeException( "not allowed [" + s + "]" );
    }

    public boolean canListen(InetSocketAddress address, ServerSession session){
        return false;
    }
    
    public boolean canConnect(InetSocketAddress address, ServerSession session){
        return false;
    }

    public void run()
        throws IOException , InterruptedException {
        _server.start();
        while ( true ){
            Thread.sleep( 1000 );
        }        
    }
    final SshServer _server;
    
}
