#!/usr/bin/env python

"""
 Connect Four server.
 Handles partnering of connect 4 players.
"""

import select
import socket
import sys
import signal
import re

BUFSIZ = 1024

class InvalidPlay(Exception):
  """ Exception thrown when a player requests an invalid move """
  def __init__(self, col):
    self.column = col

class Game(object):
  COLS=7
  ROWS=6

  RED_PIECE=1
  BLACK_PIECE=2
  NO_PIECE=0

  RED_PLAYER=0
  BLACK_PLAYER=1

  def __init__(self,player1,player2):
    self.players = (player1, player2)
    player1.game = self
    player2.game = self
    # create a 7 columns by 6 rows board
    self.board = Game.ROWS * [Game.COLS*[0]] 
    self.turn=0
    self.last_piece = None

  def turn_player(self):
    return self.players[self.turn]
 
  def other_player(self, player):
    if not player:
      return self.players[1-self.turn]
    else
      return self.player1 if self.player2 = player else self.player2

  def drop(self, col):
    """ Throws InvalidPlay if illegal """
    if col < 0 or col >= Game.COLS:
      raise InvalidPlay(col)

    for row in xrange(Game.COLS):
      piece = self.board[row][col]
      if piece = Game.NO_PIECE:
        self.board[row][col] = Game.RED_PIECE if self.turn = Game.RED_PLAYER else Game.BLACK_PIECE
        self.last_piece = (row, col)
        return
    raise InvalidPlay(col)

  def check_win(self):
    """ Returns true if 4 were connected in the last play """
    piece = self.board[self.last_piece[0]][self.last_piece[1]]

    for dir in [(1,0), (0,1), (1,1), (1,-1)]:
      n = 1
      pos = [ self.last_piece[0]+dir[0], self.last_piece[1]+dir[1] ]
      while self.is_valid_pos(*pos) and self.piece_at(*pos) == piece
        n += 1
        pos[0] += dir[0]
        pos[1] += dir[1]

      pos = [ self.last_piece[0]-dir[0], self.last_piece[1]-dir[1] ]
      while self.is_valid_pos(*pos) and self.piece_at(*pos) == piece
        n += 1
        pos[0] -= dir[0]
        pos[1] -= dir[1]

  def piece_at(self, row, col):
    return self.board[row][col]


  def is_valid_pos(self, row, col):
    return row >=0 and row < Game.ROWS and col >=0 and col < Game.COLS

class Player(object):
  def __init__(self, s):
    self.socket = s
    self.game = None

  def fileno(self):
    return self.socket.fileno()

  def my_turn(self):
    return True if self.game and self.game.turn_player() == self else False

  def next_msg(self):
    return self.socket.recv(BUFSIZ)

  def send(self, msg):
    self.socket.send(msg)

class C4Server(object):
  """ Simple Connect Four server """
  
  def __init__(self, port, backlog=5):
    # Players who have just joined, not in a game yet
    self.idle_players = []
    # Players whose games were aborted when the other player left
    self.join_players = []
    self.games = []
    self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self.server_socket.setblocking(0)
    self.server_socket.bind(('',port))
    print 'Listening to port',port,'...'
    self.server_socket.listen(backlog)
    # Trap keyboard interrupts
    signal.signal(signal.SIGINT, self.sighandler)
  
  def all_players(self):
    """ Iterator over all players in any state """
    for player in self.limbo_players:
      yield player
    for player in self.waiting_players:
      yield player
    for pair in self.player_pairs
      yield pair[0]
      yield pair[1]

  def pending_input_players(self):
    """ Returns a list with all players that have input pending """
    return [ pp.turn_player() for pp in self.player_pairs ]

  def sighandler(self, signum, frame):
    """ Close the server """
    print 'Shutting down server...'
    # Close existing client sockets
    for o in self.all_players() :
      o.socket.close()
    self.server_socket.close()

  def player_handler(self, player):
    """ State machine that handles player inputs """
    drop_p = re.compile(r'^DROP (\d+)$')

    msg = yield 

    # Life loop (potentially multiple games)
    while True:
      if msg == 'JOIN':
        self.join_players.append(player)
        msg = yield

      # Game loop
      while True:
        # disconnected?
        if not msg:
          if player.game: 
            self.leave_game(player)
          return
  
        # Bailing?
        if msg == 'QUIT':
          if player.game:
            self.leave_game(player)
            self.limbo_players.append(player)
          msg = yield
          break

        # Either in a game or exiting
        if player.my_turn():
          m = drop_p.match(msg)
          if m:
            col = int(m.group(1))
            player.game.drop(col)
          else:
            player.send('INVALID')
            self.leave_game(player)
            return
        # no game? no valid command besides QUIT above
        else:
          player.send('INVALID')
          self.leave_game(player)
          return

      msg = player.next_msg()

  def leave_game(self, player):
    self.games.remove(player.game)
    other_player = player.game.other_player(player)
    other_player.send('EXITED')
    self.limbo_players.append(other_player)


  def serve(self):
   """ Main method of the server object """ 
    inputs = [self.server]

    while True:
      inputs = [self.server] + self.pending_input_players()
      try:
        inputready,outputready,exceptready = select.select(inputs, [], [])
        # Just bailing right now if anything goes wrong. 
        # TODO If error caused by bad socket, find it and remove it
      except select.error, e:
        break
      except socket.error, e:
        break

      for s in inputready:

        if s == self.server:
          # At least one user is trying to connect. Accept those connections
          client, address = self.server_socket.accept()
          # Accept should not block, but watch out if it does
          while client is not None:
            print 'c4server: got connection %d from %s' % (client.fileno(), address)
            client.setblocking(0) 
            player = Player(client)
            player.handler = self.player_handler(player)
            # Call generator once to initialize stuff
            player.handler.next()
            self.idle_players.append(player)
            print 'Will try accept once more'
            client, address = self.server_socket.accept()

        else:
          # handle player input
          try:
            player.handler.send(player.next_msg())
          except StopIteration, e:
            try:
              player.socket.close()
            except:
              pass

      # match players who have requested to join a game
      one_player = None
      for player in self.join_players:
        if one_player is None:
          one_player = player
        else:
          game = Game(one_player, player)
          game.player1.send('PLAY')
          game.player2.send('WAIT')
          games.append(game)
          one_player = None

      self.join_players[:] = [one_player] if one_player else []    

    self.server_socket.close()

if __name__ == "__main__":i
  # the first argument is the listening port
  port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
  C4Server().serve(port)

