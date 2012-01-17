from getpass import getpass
from radius import RADIUS

host = "127.0.0.1"
port = 1812

secret = ''
uname,passwd = None,None
while not secret: secret = getpass('RADIUS Secret? ')
while not uname:  uname  = raw_input("Username? ")
while not passwd: passwd = getpass("Password? ")

r = RADIUS(secret,host,port)
r.timeout = 10


if r.authenticate(uname,passwd):
    print "Authentication Succeeded"
else:
    print "Authentication Failed"
