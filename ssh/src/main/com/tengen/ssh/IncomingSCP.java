// SCP.java

package com.tengen.ssh;

import java.io.*;
import java.net.*;
import java.util.*;
import java.util.regex.*;
import java.util.concurrent.atomic.*;
import java.text.*;

import org.apache.sshd.*;
import org.apache.sshd.server.*;
import org.apache.sshd.common.*;
import org.apache.sshd.server.keyprovider.*;
import org.apache.sshd.server.shell.*;
import org.apache.sshd.server.command.*;
import org.apache.sshd.server.session.*;

public class IncomingSCP implements Command, Runnable {
    
    static File ROOT = new File( "/data/incoming-scp/" );
    
    static enum Mode { NONE, READ, WRITE };
    
    Mode _mode = Mode.NONE;
    String _filePrefix;
    String _user;
    boolean _recusrive = false;
    
    InputStream _in;
    OutputStream _out;
    OutputStream _err;
    ExitCallback _exit;

    void info( String s ){
        System.out.println( "ScpCommand: " + s );
    }
    
    public IncomingSCP(String[] args , boolean writeOnly ){
        if ( ! args[0].equals( "scp" ) )
            throw new IllegalArgumentException( "first arg has to be scp" );
        
        for ( int i=1; i<args.length; i++){
            if ( args[i].charAt(0) == '-' ){
                for (int j = 1; j < args[i].length(); j++) {
                    switch (args[i].charAt(j)) {
                    case 'r':
                        _recusrive = true;
                        break;
                    case 'p':
                    case 'v':
                        break;
                    case 'f': // read
                        if ( writeOnly )
                            throw new IllegalArgumentException( "can't read" );
                        if ( _mode != Mode.NONE )
                            throw new IllegalArgumentException( "can't have -f and -t" );
                        _mode = Mode.READ;
                        break;
                    case 't': // read
                        if ( _mode != Mode.NONE )
                            throw new IllegalArgumentException( "can't have -f and -t" );
                        _mode = Mode.WRITE;
                        break;
                    default:
                        throw new IllegalArgumentException( "Unsupported option: " + args[i].charAt(j) );
                    }
                }
            } 
            else if (i == args.length - 1) {
                _filePrefix = args[i];
            }
        }
    }

    public void setInputStream(InputStream in) {
        _in = in;
    }

    public void setOutputStream(OutputStream out) {
        _out = out;
    }

    public void setErrorStream(OutputStream err) {
        _err = err;
    }

    public void setExitCallback(ExitCallback callback) {
        _exit = callback;
    }

    public void start(Environment env) throws IOException {
        _user = env.getEnv().get( "USER" );
        if ( _user == null ){
            _out.write( "need user".getBytes() );
            return;
        }
            
        new Thread(this).start();
    }

    public void destroy() {
    }
    
    public void run() {
        int exitValue = 0;
        String exitMessage = "";

        File root = new File( ROOT , shortDate() + "/" + _user + "/" + clean( _filePrefix ) + "/" );
        
        try {
            if ( _mode == Mode.READ ){
                throw new IOException( "can't read yet" );
            }
            else if ( _mode == Mode.WRITE ){
                ack();
                if ( _recusrive )
                    writeDir( readLine() , root );
                else
                    writeFile( readLine() , root );
            }
            else {
                throw new IllegalStateException();
            }
        } 
        catch (IOException e) {
            e.printStackTrace();
            
            try {
                exitValue = -2;
                exitMessage = e.toString();
                
                _out.write(exitValue);
                _out.write(exitMessage.getBytes());
                
                _out.write('\n');
                _out.flush();
            } catch (IOException e2) {
                // Ignore
            }
            
        } 
        finally {
            if ( _exit != null ){
                _exit.onExit(exitValue, exitMessage);
            }
        }
    }
    protected void writeDir(String header, File path) throws IOException {
        info( "Writing dir: " + path );
        
        if (!header.startsWith("D")) {
            throw new IOException("Expected a D message but got '" + header + "'");
        }

        String perms = header.substring(1, 5);
        int length = Integer.parseInt(header.substring(6, header.indexOf(' ', 6)));
        String name = header.substring(header.indexOf(' ', 6) + 1);

        if (length != 0) {
            throw new IOException("Expected 0 length for directory but got " + length);
        }

        File file = new File( path , clean( name ) );

        ack();

        for (;;) {
            header = readLine();
            if (header.startsWith("C")) {
                writeFile(header, file);
            } else if (header.startsWith("D")) {
                writeDir(header, file);
            } else if (header.equals("E")) {
                ack();
                break;
            } else {
                throw new IOException("Unexpected message: '" + header + "'");
            }
        }

    }

    protected void writeFile(String header, File path) throws IOException {
        info( "writeFile: " + path );
        
        if (!header.startsWith("C")) {
            throw new IOException("Expected a C message but got '" + header + "'");
        }

        String perms = header.substring(1, 5);
        long length = Long.parseLong(header.substring(6, header.indexOf(' ', 6)));
        String name = header.substring(header.indexOf(' ', 6) + 1);
        
        System.out.println( "perms: " + perms + " length: " + length + " name: " + name );
        
        if ( ! path.exists() )
            path.mkdirs();
        
        if ( ! ( path.exists() && path.isDirectory() ) )
            throw new IOException( "bad dir [" + path + "]" );
        
        File f = new File( path , clean( name ) );
        System.out.println( "going to : " + f );
                
        FileOutputStream out = new FileOutputStream(f);
        try {
            ack();

            byte[] buffer = new byte[8192];
            while (length > 0) {
                int len = (int) Math.min(length, buffer.length);
                len = _in.read(buffer, 0, len);
                if (len <= 0) {
                    throw new IOException("End of stream reached");
                }
                out.write(buffer, 0, len);
                length -= len;
            }
        } finally {
            out.close();
        }

        ack();
        readAck();
    }

    /*

    protected void readFile(File path) throws IOException {
        if (log.isDebugEnabled()) {
            log.debug("Reading file {}", path);
        }
        StringBuffer buf = new StringBuffer();
        buf.append("C");
        buf.append("0644"); // what about perms
        buf.append(" ");
        buf.append(path.length()); // length
        buf.append(" ");
        buf.append(path.getName());
        buf.append("\n");
        out.write(buf.toString().getBytes());
        out.flush();
        readAck();

        InputStream is = new FileInputStream(path);
        try {
            byte[] buffer = new byte[8192];
            for (;;) {
                int len = is.read(buffer, 0, buffer.length);
                if (len == -1) {
                    break;
                }
                out.write(buffer, 0, len);
            }
        } finally {
            is.close();
        }
        ack();
        readAck();
    }

    protected void readDir(File path) throws IOException {
        if (log.isDebugEnabled()) {
            log.debug("Reading directory {}", path);
        }
        StringBuffer buf = new StringBuffer();
        buf.append("D");
        buf.append("0755"); // what about perms
        buf.append(" ");
        buf.append("0"); // length
        buf.append(" ");
        buf.append(path.getName());
        buf.append("\n");
        out.write(buf.toString().getBytes());
        out.flush();
        readAck();

        for (File child : path.listFiles()) {
            if (child.isFile()) {
                readFile(child);
            } else if (child.isDirectory()) {
                readDir(child);
            }
        }

        out.write("E\n".getBytes());
        out.flush();
        readAck();
    }
    */

    protected String readLine() 
        throws IOException {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        for (;;) {
            int c = _in.read();
            if ( c == '\r' )
                continue;
            
            if (c  == '\n' )
                return baos.toString();
            
            if (c == -1)
                throw new IOException("End of stream");
                
            baos.write(c);
        }
    }


    protected void ack() throws IOException {
        _out.write(0);
        _out.flush();
    }

    protected void readAck() throws IOException {
        int c = _in.read();
        switch (c) {
            case 0:
                break;
            case 1:
                System.out.println("Received warning: " + readLine());
                break;
            case 2:
                throw new IOException("Received nack: " + readLine());
        }
    }
    
    String shortDate(){
        SimpleDateFormat f = new SimpleDateFormat( "yyyy-MM-dd-HH-mm" );
        return f.format( new Date() );
    }
    
    String clean( String s ){
        while ( true ){
            int before = s.length();
            s = s.replace( ".." , "." ) ;
            s = s.replace( "/./" , "/" );
            if ( before == s.length() )
                return s;
        }
    }
}

