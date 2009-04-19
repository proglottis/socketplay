"""
Game client
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import pyglet

from protocol import command, dispatch
import sockwrap

class ClientBoxman(pyglet.sprite.Sprite):
    """Client Boxman entity"""
    def __init__(self, color=(255, 255, 255), batch=None, group=None):
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
        super(ClientQuit, self).__init__()
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
    client = Client(batch, sock_server, hellocmd, quitcmd, clientcmd, sendto,
                    players)
    return client
