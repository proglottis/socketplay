"""
SocketPlay

Simple client/server python game.
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import optparse
import random
import struct

import pyglet

from protocol import command, dispatch
from util import IdentAlloc, IdentFetchError
import sockwrap

logging.basicConfig(level=logging.DEBUG)

class ServerBoxman(object):
    """Server Boxman entity"""
    SPEED = 100
    COLORS = (
        (0, 0, 255),
        (0, 255, 0),
        (0, 255, 255),
        (255, 0, 0),
        (255, 0, 255),
        (255, 255, 0),
        (255, 255, 255),
    )

    def __init__(self, id):
        self.id = id
        self.color = random.choice(self.COLORS)
        self.x = 0
        self.y = 0
        self.north = False
        self.east = False
        self.south = False
        self.west = False

    def get_position(self):
        return (self.x, self.y)

    def set_position(self, x, y):
        self.x = x
        self.y = y

    def set_direction(self, direction):
        self.north, self.east, self.south, self.west = direction

    def update(self, dt):
        speed = self.SPEED * dt
        if self.north:
            self.y += speed
        if self.south:
            self.y -= speed
        if self.west:
            self.x -= speed
        if self.east:
            self.x += speed

class ServerBoxmanFactory(object):
    """Server Boxman entity factory"""
    def create(self, id):
        return ServerBoxman(id)

class Server(object):
    """Handle updating entities and socket server"""
    def __init__(self, sock_server, updatecmd, players):
        self.sock_server = sock_server
        self.updatecmd = updatecmd
        self.players = players

    def update(self, dt):
        for player in self.players.itervalues():
            player.update(dt)
        for address in self.players.iterkeys():
            self.updatecmd.send(self.players.values(), address)
        self.sock_server.update()

def create_server(address, port=11235):
    """Server creation factory method"""
    players = {}
    idalloc = IdentAlloc(256)
    sock_writequeue = sockwrap.SocketWriteQueue()
    boxmanfactory = ServerBoxmanFactory()
    headpack = command.HeaderPack(sock_writequeue)
    cmdpack = command.CommandPack(headpack)
    quitcmd = command.QuitCommand(cmdpack)
    spawncmd = command.SpawnCommand(cmdpack)
    destroycmd = command.DestroyCommand(cmdpack)
    updatecmd = command.UpdateCommand(cmdpack)
    hello = dispatch.ServerHelloDispatch(spawncmd, players, idalloc,
                                         boxmanfactory)
    quit = dispatch.ServerQuitDispatch(quitcmd, destroycmd, players, idalloc)
    client = dispatch.ServerClientDispatch(players)
    cmd = dispatch.ServerCommandDispatch(hello, quit, client)
    header = dispatch.HeaderDispatch(cmd)
    sock_dispatcher = sockwrap.SocketReadDispatch(header)
    sock = sockwrap.create_server_socket(address, port)
    sock_server = sockwrap.SocketServer(sock_dispatcher, sock_writequeue, sock)
    server = Server(sock_server, updatecmd, players)
    return server

class ClientBoxman(pyglet.sprite.Sprite):
    """Client Boxman entity"""
    def __init__(self, color=(255,255,255), batch=None, group=None):
        super(ClientBoxman, self).__init__(
                pyglet.resource.image('boxman.png'),
                batch=batch, group=group)

class ClientBoxmanFactory(object):
    """Client Boxman entity factory"""
    def __init__(self, batch):
        self.batch = batch

    def create(self, color):
        return ClientBoxman(color, batch=self.batch)

class ClientQuit(pyglet.event.EventDispatcher):
    """Dispatch packet unwrapping client quit command"""
    def __init__(self):
        self.quit = False

    def set_quit(self):
        self.quit = True
        self.dispatch_event('on_quit')

    def is_quit(self):
        return self.quit

ClientQuit.register_event_type('on_quit')

class Client(object):
    """Handle updating and rendering client entities and socket server"""
    def __init__(self, batch, sock_server, hellocmd, quitcmd, clientcmd,
                 sendto,
                 players):
        self.batch = batch
        self.sock_server = sock_server
        self.hellocmd = hellocmd
        self.quitcmd = quitcmd
        self.clientcmd = clientcmd
        self.sendto = sendto
        self.players = players
        self.north = False
        self.east = False
        self.south = False
        self.west = False
        self.changed = False

    def send_hello(self):
        self.hellocmd.send(self.sendto)

    def send_quit(self):
        self.quitcmd.send(self.sendto)

    def send_client(self):
        if self.changed:
            dir = (self.north, self.east, self.south, self.west)
            self.clientcmd.send(dir, self.sendto)
            self.changed = False

    def start_move(self, north=False, east=False, south=False, west=False):
        self.north = self.north or north
        self.east = self.east or east
        self.south = self.south or south
        self.west = self.west or west
        self.changed = north or east or south or west

    def stop_move(self, north=False, east=False, south=False, west=False):
        self.north = self.north and not north
        self.east = self.east and not east
        self.south = self.south and not south
        self.west = self.west and not west
        self.changed = north or east or south or west

    def update(self, dt):
        self.send_client()
        self.sock_server.update()
        self.batch.draw()

def create_client(quit_flag, address, port=11235):
    """Client creation factory method"""
    players = {}
    batch = pyglet.graphics.Batch()
    boxmanfactory = ClientBoxmanFactory(batch)
    quit_dispatcher = dispatch.ClientQuitDispatch(quit_flag)
    spawn_dispatcher = dispatch.ClientSpawnDispatch(players, boxmanfactory)
    destroy_dispatcher = dispatch.ClientDestroyDispatch(players)
    update_dispatcher = dispatch.ClientUpdateDispatch(players)
    cmd_dispatcher = dispatch.ClientCommandDispatch(quit_dispatcher,
                                                    spawn_dispatcher,
                                                    destroy_dispatcher,
                                                    update_dispatcher)
    header_dispatcher = dispatch.HeaderDispatch(cmd_dispatcher)
    sock_dispatcher = sockwrap.SocketReadDispatch(header_dispatcher)
    sock_writequeue = sockwrap.SocketWriteQueue()
    headpack = command.HeaderPack(sock_writequeue)
    cmdpack = command.CommandPack(headpack)
    hellocmd = command.HelloCommand(cmdpack)
    quitcmd = command.QuitCommand(cmdpack)
    clientcmd = command.ClientCommand(cmdpack)
    sock = sockwrap.create_client_socket()
    sendto = (address, port)
    sock_server = sockwrap.SocketServer(sock_dispatcher, sock_writequeue, sock)
    client = Client(batch,sock_server, hellocmd, quitcmd, clientcmd, sendto,
                    players)
    return client

class MainWindow(pyglet.window.Window):
    def __init__(self, client):
        super(MainWindow, self).__init__()
        self.clock = pyglet.clock.ClockDisplay()
        self.batch = client.batch
        self.client = client

    def on_key_press(self, symbol, modifiers):
        if symbol == pyglet.window.key.UP:
            self.client.start_move(north=True)
        elif symbol == pyglet.window.key.RIGHT:
            self.client.start_move(east=True)
        elif symbol == pyglet.window.key.DOWN:
            self.client.start_move(south=True)
        elif symbol == pyglet.window.key.LEFT:
            self.client.start_move(west=True)
        elif symbol == pyglet.window.key.ESCAPE:
            self.client.send_quit()

    def on_key_release(self, symbol, modifiers):
        if symbol == pyglet.window.key.UP:
            self.client.stop_move(north=True)
        elif symbol == pyglet.window.key.RIGHT:
            self.client.stop_move(east=True)
        elif symbol == pyglet.window.key.DOWN:
            self.client.stop_move(south=True)
        elif symbol == pyglet.window.key.LEFT:
            self.client.stop_move(west=True)

    def on_client_quit(self):
        self.close()

    def on_draw(self):
        self.clear()
        self.batch.draw()
        self.clock.draw()

def main(server=True, address="localhost", port=11235):
    """Entry point"""
    quit_flag = ClientQuit()
    if server:
        logging.debug("Start server")
        server = create_server("0.0.0.0", port)
        pyglet.clock.schedule_interval(server.update, 1/30.0)
    logging.debug("Start client")
    client = create_client(quit_flag, address, port)
    client.send_hello()
    pyglet.clock.schedule_interval(client.update, 1/60.0)
    logging.debug("Open window")
    window = MainWindow(client)
    quit_flag.push_handlers(on_quit=window.on_client_quit)
    pyglet.app.run()

if __name__ == "__main__":
    parser = optparse.OptionParser()
    parser.set_defaults(server=True)
    parser.add_option("-s", "--server", action="store_true", dest="server",
                      help="run server and client connecting to ADDRESS "
                           "via PORT")
    parser.add_option("-c", "--client", action="store_false", dest="server",
                      help="run client connecting to ADDRESS via PORT")
    parser.add_option("-a", "--address", type="string", dest="address",
                      default="localhost", help="set IP address to listen "
                              "or connect to")
    parser.add_option("-p", "--port", type="int", dest="port", default=11235,
                      help="set port to listen or connect to")
    (options, args) = parser.parse_args()
    main(server=options.server, address=options.address, port=options.port)
