#!/usr/bin/python
##server.py
from socket import *      #import the socket library

##let's set up some constants
HOST = ''    #we are the host
PORT = 8043    #arbitrary port not currently in use
ADDR = (HOST,PORT)    #we need a tuple for the address
BUFSIZE = 4096    #reasonably sized buffer for data

## now we create a new socket object (serv)
## see the python docs for more information on the socket types/flags
serv = socket(AF_INET,SOCK_STREAM)    

##bind our socket to the address
serv.bind((ADDR))    #the double parens are to create a tuple with one element
serv.listen(5)    #5 is the maximum number of queued connections we'll allow

print 'listening on port',PORT

while True :  
  conn,addr = serv.accept() # block and accept the next connection
  print '...connected! Sending policy'
  conn.send("""<?xml version="1.0"?>
<cross-domain-policy>
<allow-access-from domain="*" to-ports="8080"/>
</cross-domain-policy>""")

  conn.close()

print 'Exiting'
