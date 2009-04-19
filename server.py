"""
Game server
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import random

from protocol import command, dispatch
from util import IdentAlloc
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
