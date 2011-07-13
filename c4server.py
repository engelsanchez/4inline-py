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
import errno

BUFSIZ = 1024

class InvalidPlay(Exception):
  """ Exception thrown when a player requests an invalid move """

  def __init__(self, col):
    self.column = col

  def __str__(self):
    return "Invalid move on column : " + col


class InvalidCommand(Exception):
  """ Indicates the user has sent an invalid or unexpected command """

  def __init(self,msg):
    self.msg = msg

  def __str__(self):
    return "Invalid command : " + msg


class PlayerSocketError(Exception):
  """ Raised when a player connection is broken """
  def __init__(self, player, socket_error = None):
    self.player = player
    self.socket_error = socket_error


class Game(object):
  """ Contains two players and a board """
  COLS=7
  ROWS=6

  RED_PIECE=1
  BLACK_PIECE=2
  NO_PIECE=0

  RED_PLAYER=0
  BLACK_PLAYER=1

  game_num = 0

  def __init__(self,player1,player2):
    Game.game_num += 1
    self.game_num = Game.game_num
    self.players = [player1, player2]
    player1.game = self
    player2.game = self
    # create a 7 columns by 6 rows board
    self.board = [Game.COLS*[Game.NO_PIECE] for i in xrange(Game.ROWS)] 
    self.turn=0
    self.last_piece = None

  def __str__(self):
    return "Game %i (%s, %s)" % (self.game_num, self.players[0], self.players[1])

  def turn_player(self):
    return self.players[self.turn]

  def other_player(self, player):
    if not player:
      return self.players[1-self.turn]
    else:
      return self.players[0] if self.players[1] == player else self.players[1]

  def remove_player(self, player):
    """ Removes player from game """
    if self.players[0] == player:
      self.players[0] = None
    elif self.players[1] == player:
      self.players[1] = None

  def drop(self, col):
    """ 
    Perform a piece drop on a column of the board and return win status.
    Throws InvalidPlay if illegal 
    """
    if col < 0 or col >= Game.COLS:
      raise InvalidPlay(col)

    for row in xrange(len(self.board)):
      piece = self.board[row][col]
      print 'piece in %i,%i is %i' % (row,col,piece)
      if piece == Game.NO_PIECE:
        print 'Placed piece in (%i,%i) ' % (row,col)
        self.board[row][col] = Game.RED_PIECE if self.turn == Game.RED_PLAYER else Game.BLACK_PIECE
        self.last_piece = (row, col)
        self.print_board()
        return self.check_win()
    raise InvalidPlay(col)

  def print_board(self):
    """ Simple debug print of a game board """
    print
    for row in self.board[::-1]:
      print "  ",
      for col in row:
        print col,
      print
    print

  def check_win(self):
    """ Returns true if 4 were connected in the last play """
    piece = self.board[self.last_piece[0]][self.last_piece[1]]

    n = 1
    for dir in [(1,0), (0,1), (1,1), (1,-1)]:
      pos = [ self.last_piece[0] + dir[0], self.last_piece[1] + dir[1] ]
      while self.is_valid_pos(*pos) and self.piece_at(*pos) == piece:
        n += 1
        pos[0] += dir[0]
        pos[1] += dir[1]

      pos = [ self.last_piece[0] - dir[0], self.last_piece[1] - dir[1] ]
      while self.is_valid_pos(*pos) and self.piece_at(*pos) == piece:
        n += 1
        pos[0] -= dir[0]
        pos[1] -= dir[1]
    return n >= 4

  def piece_at(self, row, col):
    return self.board[row][col]

  def is_valid_pos(self, row, col):
    return row >=0 and row < Game.ROWS and col >=0 and col < Game.COLS


class Player(object):
  """ Information about a player and its associated network socket """

  # Gets incremented and assigned to each new player
  player_num = 0  

  def __init__(self, s, address):
    self.socket = s
    self.address = address
    self.game = None
    # Totally not thread safe for future reference
    Player.player_num += 1
    self.player_num = Player.player_num

  def __str__(self):
    return "Player %i from %s" % (self.player_num, self.address)

  def fileno(self):
    """ Defined so Player can be passed to select.select() """
    return self.socket.fileno()

  def my_turn(self):
    """ Returns true if it is this player's turn """
    return True if self.game and self.game.turn_player() == self else False

  def next_msg(self):
    """ 
    Returns the next command sent from this player without the command terminator
    or possibly empty if the connection has been dropped
    """
    try:
      msg = self.socket.recv(BUFSIZ)
    except socket.error as se:
      raise PlayerSocketError(self, se)
    if not msg:
      return msg
    # messages must end in ';' right now. 
    # if clients send multiple messages, we're only reading the last
    # This needs to be improved with a better msg protocol later
    if not msg.endswith(';'):
      raise InvalidCommand('Player sent '+msg)
    # Return message before the last ';'
    return msg.split(';')[-2]

  def send(self, msg):
    try:
      print 'Sending message',msg,'to player',self
      self.socket.sendall(msg+';')
    except socket.error as e:
      raise PlayerSocketError(self, e)


class C4Server(object):
  """ Simple Connect Four server """

  def __init__(self, port, backlog=5):
    # Players who have just joined, or were kicked out of a game, or finished a game 
    self.idle_players = []
    # Players who have requested to join a game 
    self.join_players = []
    self.games = []
    # Create non-blocking listening socket
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
    for player in self.idle_players:
      yield player
    for player in self.join_players:
      yield player
    for game in self.games:
      yield game.players[0]
      yield game.players[1]

  def sighandler(self, signum, frame):
    """ Close the server """
    print 'Shutting down server...'
    # Close existing client sockets
    for o in self.all_players() :
      o.socket.close()
    self.server_socket.close()

  def player_handler(self, player):
    """ 
    Generator that acts as a state machine that handles player inputs.
    This is the meat of this server!!
    """
    print "Init for player",player
    player.send("CONNECT4")

    # Life loop (potentially multiple games)
    while True:
      msg = yield
      # disconnect?
      if not msg:
        return
      if msg == 'QUIT':
        self.handle_player_quit(player)
      elif not player.game:# Not yet in a game
        if msg == 'JOIN':
          self.handle_join(player)
        else:
          player.send('INVALID_COMMAND')
      elif player.my_turn():
        try:
          if self.handle_player_move(player,msg):
            self.handle_win(player.game)
        except InvalidCommand as e:
          player.send('INVALID_COMMAND')
        except InvalidPlay as e:
          player.send('INVALID_MOVE')
      else:
        player.send('INVALID_COMMAND')

  def handle_join(self, player):
    """ Handle join action """
    print "Join from ",player
    if self.idle_players.count(player):
      self.idle_players.remove(player)
    self.join_players.append(player)
    player.send('JOINED')

  def handle_win(self, game):
    winning_player = game.turn_player()
    winning_player.send('YOU_WIN')
    losing_player = game.other_player(winning_player)
    losing_player.send('YOU_LOSE')
    self.idle_players.extend((winning_player, losing_player))
    self.games.remove(game)

  def handle_player_quit(self, player):
    """ 
    Handles player quit action in the middle of a game or waiting to join a game.
    The player goes back to idle state and can later try to join a game.
    """
    print "quit action ",player
    if self.join_players.count(player):
      self.join_players.remove(player)
    self.idle_players.append(player)
    if not player.game:
      return
    self.games.remove(player.game)
    player.game.remove_player(player)
    other_player = player.game.other_player(player)
    if other_player:
      other_player.send('EXITED')
      self.limbo_players.append(other_player)

  drop_p = re.compile(r'^DROP (\d+)$')

  def handle_player_move(self, player, msg):
    """ During a player's turn, accept the next move command """
    print 'Player move:', msg, "from", player
    m = C4Server.drop_p.match(msg)
    if m:
      col = int(m.group(1))
      print "Drop in column", col
      won = player.game.drop(col)
      player.game.other_player(player).send('DROPPED %i' % (col))
      return won
    else:
      raise InvalidCommand(msg)

  def disconnect_player(self, player):
    """ Handles player disconnection """
    print 'disconnecting player',player
    self.handle_player_quit(player)
    if self.idle_players.count(player):
      self.idle_players.remove(player)
    try:
      player.socket.close()
    except Exception as e:
      print "On socket close : ", e
      pass

  def handle_invalid_command(self, player):
    self.disconnect_player(player)

  def handle_new_connections(self):
    # At least one user is trying to connect. Accept those connections
    client, address = self.server_socket.accept()
    # Accept should not block, but watch out if it does
    while client is not None:
      print 'c4server: got connection %d from %s' % (client.fileno(), address)
      client.setblocking(0)
      player = Player(client, address)
      player.handler = self.player_handler(player)
      # Call generator once to initialize stuff
      player.handler.next()
      self.idle_players.append(player)
      client, address = None, None
      try:
        print "Will try to accept another"
        client, address = self.server_socket.accept()
      except socket.error as e:
        if e[0] == errno.EWOULDBLOCK:
          print "Nope, no more"
          break;
        if e[0] == errno.EAGAIN:
          print "Fancy that, got EAGAIN. Leave it until next time "
          continue
        raise

  def match_players(self):
    # match players who have requested to join a game
    one_player = None   
    print "Will try to match", len(self.join_players),"in games"
    for player in self.join_players[:]:
      if one_player is None:
        one_player = player
      else:
        game = Game(one_player, player)
        # TODO These sends can fail and need to be handled
        game.players[0].send('PLAY')
        game.players[1].send('WAIT')
        self.games.append(game)
        print "Added game", game
        one_player = None
    self.join_players[:] = [one_player] if one_player else []

  def serve(self):
    """ Main method of the server object """
    try:
      while True:
        inputs = [self.server_socket]
        inputs.extend(self.all_players())
        try:
          print "%i games, %i idle, %i join" % (
                   len(self.games), len(self.idle_players),len(self.join_players))
          print "Will call select with %i input sockets " % (len(inputs))
          inputready,outputready,exceptready = select.select(inputs, [], [])
          print "Select returned with %i ready sockets " % (len(inputready))
          # Just bailing right now if anything goes wrong. 
          # TODO If error caused by bad socket, find it and remove it
        except select.error as e:
          print "Select error : ", e
          break
        except socket.error as e:
          print "Socket error ", e
          self.remove_bad_sockets(inputs)
          continue
        except Exception as e:
          print "Unexpected exception in select : ", e
          break
        self.handle_messages(inputready)
        # Pair up players who requested to join a game
        self.match_players()
    finally:
      print "Closing socket server"    
      self.server_socket.close()

  def remove_bad_sockets(self, inputs):
    """ Find and remove player sockets in a bad state """
    # Find the offending socket
    for player in inputs[:]:
      try:
        select.select([player],[],[], 0)
      except socket.error as se:
        self.disconnect_player(player)

  def handle_messages(self, inputready):
    for s in inputready:
      if s == self.server_socket:
        self.handle_new_connections()
      else:
        player = s
        print "Will handle messages from player", player
        try:
          player.handler.send(player.next_msg())
        # Handle normal exit
        except StopIteration as e:
          self.disconnect_player(player)
        except PlayerSocketError as e:
          print "Player",e.player," disconnected with error ", e.socket_error  
          self.disconnect_player(e.player)

if __name__ == "__main__":
  # the first argument is the listening port
  port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
  C4Server(port).serve()

