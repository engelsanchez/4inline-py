#!/usr/bin/env python

"""
 Connect Four test client.
 Handles partnering of connect 4 players.
"""

import select
import socket
import sys
import signal
import re
import errno

class C4Client(object):
  """ Connect 4 test client """
  BUFSIZ = 4096

  def connect(self, server, port):
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      self.socket.connect((server, port))
    except socket.error as e:
      print "Error connecting to server %s on port %i : %s" % (server, port, e)
      raise

    try:
      while True:
        userInt = False
        print 'Waiting for server message...'
        try:
          msg = self.socket.recv(C4Client.BUFSIZ)
        except socket.error as e:
          if e[0] == errno.EAGAIN:
            continue
          raise
        except KeyboardInterrupt as e:
          userInt = True
        if msg:
          print "Received :",msg
        if not msg and not userInt:
          break
        try:
          msg = raw_input(">> ")
        except KeyboardInterrupt as e:
          print
          msg = None
        if msg:
          print "Will send message:",msg
          msg = msg if msg.endswith(';') else msg + ';'
          self.socket.sendall(msg.upper())
    except Exception as e:
      print "Ended with exception", e
    finally:
      print "Closing socket"
      self.socket.close()


if __name__ == "__main__":
  # the first argument is the listening port 
  server = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
  port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
  C4Client().connect(server, port)

