// CommandBase.java

package com.tengen.ssh;

import java.io.*;

import org.apache.sshd.server.*;

public abstract class CommandBase implements Command , Runnable {
    
    public void setInputStream(InputStream in){
        _in = in;
    }
    
    public void setOutputStream(OutputStream out){
        _out = out;
    }
    
    public void setErrorStream(OutputStream err){
        _err = err;
    }
    
    public void setExitCallback(ExitCallback callback){
        // TODO
    }
    
    public void start(Environment env)
        throws IOException {
        _env = env;
        assert( _in != null );
        assert( _out != null );
        assert( _err != null );
        assert( _t == null );
        
        _killed = false;
        _t = new Thread( this );
        _t.start();
    }
    
    public void destroy(){
        _killed = true;
        try {
            _t.interrupt();
            _t.join();
        }
        catch ( InterruptedException ie ){
        }
    }
    
    protected InputStream _in;
    protected OutputStream _out;
    protected OutputStream _err;
    protected Environment _env;
    
    protected Thread _t = null;
    protected boolean _killed;
    
}
