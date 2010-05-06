// SupportSSH.java

package com.tengen;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.concurrent.atomic.*;

import org.apache.sshd.*;
import org.apache.sshd.server.*;
import org.apache.sshd.common.*;
import org.apache.sshd.server.keyprovider.*;
import org.apache.sshd.server.shell.*;
import org.apache.sshd.server.command.*;
import org.apache.sshd.server.session.*;

import com.tengen.ssh.*;

public class SupportSSH extends SSHBase {
    
    public Command create(){
        return new FakeShell();
    }

    class FakeShell extends CommandBase {

        String user(){
            return _env.getEnv().get( Environment.ENV_USER );
        }

        void prompt()
            throws IOException {
            _out.write( ( user() + "@mongosupport > " ).getBytes() );
            _out.flush();
        }
        
        public void run(){
            UserInfo user = getUser( user() );
            try {

                if ( user._logins <= 1 ){
                    String s = "\r\n";
                    s += "welcome to mongo ssh support!\r\n";
                    s += "your assigned port is : " + user._port + "\r\n";
                    s += "please recconect with:\r\n";
                    s += "ssh -R " + user._port + ":<local host>:<local port> " + user._user + "@sshsupport@10gen.com\r\n";
                    s += "likely:\r\n";
                    s += "ssh -R " + user._port + ":127.0.0.1:27017 " + user._user + "@sshsupport.10gen.com\r\n";
                    s += "remember, you need to login with the same password you just did\r\n";
                    _out.write( s.getBytes() );
                    _out.flush();
                    return;
                }

                {
                    String s = "yay! you made it back on the right port: " + user._port + "\r\n";
                    s += "someone shouldbe with you shortly\r\n";
                    s += "type exit to exit immediately\r\n\r\n";
                    _out.write( s.getBytes() );
                    _out.flush();
                }

                prompt();
                
                StringBuilder line = new StringBuilder();
                while ( ! _killed ){
                    int x = _in.read();
                    if ( x < 0 )
                        return;
                    
                    char c = (char)x;
                    if ( c != '\r' && c != '\n' ){
                        line.append( c );
                        _out.write( x );
                        _out.flush();
                        continue;
                    }

                    String s = line.toString().trim();
                    System.out.println( "line [" + s + "]" );
                    line.setLength( 0 );
                    
                    if ( s.equalsIgnoreCase( "exit" ) ){
                        _out.write( "\r\nbye\r\n".getBytes() );
                        _out.flush();
                        _out.close();
                        _in.close();
                        _err.close();
                        return;
                    }
                    
                    _out.write( "\r\n".getBytes() );

                    _out.write( ( "\t" + s + "\r\n" ).getBytes() );
                    prompt();
                }
                
            }
            catch ( IOException ioe ){
                ioe.printStackTrace();
                return;
            }
            finally {
                user._session.close( true );
                user._session = null;
            }
        }
    }
        
    public boolean authenticate(String username, String password, ServerSession session){
        if ( username.equals( "root" ) )
            return password.equals( "theback17" );

        UserInfo u = getUser( username );
        if ( u == null ){
            System.out.println( "new user : " + username );
            u = new UserInfo( username , password );
            u.loggedIn( session );
            _users.put( username.toLowerCase() , u );
            return true;
        }
        
        u.log( "login attempt" );
        if ( u._session != null ){
            u.log( "already have session" );
            return false;
        }
        
        if ( ! password.equals( u._pass ) ){
            u.log( "invalid pass" );
            return false;
        }

        u.log( "success" );
        u.loggedIn( session );
        return true;
    }
    
    public boolean canListen(InetSocketAddress address, ServerSession session){
        System.out.println( "wants to listen  username:" + session.getUsername() + " address: " + address );

        
        UserInfo u = getUser( session );
        if ( u._port != address.getPort() ){
            u.log( "bad listen port: " + address );
            return false;
        }
        
        if ( ! address.getHostName().equalsIgnoreCase( "localhost" ) ){
            u.log( "bad host: " + address );
            return false;
        }

        return true;
    }

    UserInfo getUser( ServerSession session ){
        return getUser( session.getUsername() );
    }
    
    UserInfo getUser( String username ){
        username = username.toLowerCase();
        return _users.get( username );
    }

    class UserInfo {
        UserInfo( String user , String pass ){
            _user = user;
            _pass = pass;
            _port = _nextPort.incrementAndGet();
        }
        
        void log( String msg ){
            System.out.println( "user [" + _user + "] " + msg );
        }

        void loggedIn( ServerSession session ){
            _session = session;
            _logins++;
        }

        final String _user;
        final String _pass;
        final int _port;
        
        int _logins = 0;
        ServerSession _session;
    }
    
    final Map<String,UserInfo> _users = Collections.synchronizedMap( new HashMap<String,UserInfo>() );
    final AtomicInteger _nextPort = new AtomicInteger( 29000 );
    
    public static void main( String args[] )
        throws Exception {
        
        SupportSSH s = new SupportSSH();
        s.run();

    }
}
