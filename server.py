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
import math
import random

from protocol import command, dispatch
from protocol.local import *
from util import IdentAlloc
import sockwrap
import physics
import vector

logger = logging.getLogger(__name__)

class ServerBoxman(object):
    """Server Boxman entity"""
    THRUST = 500.0
    ANGULAR_THRUST = 20.0
    COLORS = (
        (0, 0, 255),
        (0, 255, 0),
        (0, 255, 255),
        (255, 0, 0),
        (255, 0, 255),
        (255, 255, 0),
    )

    def __init__(self, id):
        self.id = id
        self.color = random.choice(self.COLORS)
        self.forward = False
        self.backward = False
        self.rot_cw = False
        self.rot_ccw = False
        self.body = physics.Body(10.0, 10.0)

    def get_position(self):
        return self.body.position

    def get_velocity(self):
        return self.body.velocity

    def get_direction(self):
        return self.body.angle

    def get_angle(self):
        return self.body.angle

    def set_movement(self, movement):
        self.forward, self.backward, self.rot_cw, self.rot_ccw = movement

    def update(self, dt):
        force = vector.Vec2()
        angular_force = 0.0
        if self.rot_cw:
            angular_force += self.ANGULAR_THRUST
        if self.rot_ccw:
            angular_force -= self.ANGULAR_THRUST
        if self.forward:
            force = force + \
                    vector.Vec2.from_angle(-self.get_angle(), self.THRUST)
        if self.backward:
            force = force - \
                    vector.Vec2.from_angle(-self.get_angle(), self.THRUST)
        self.body.reset_force()
        self.body.add_force(force)
        self.body.reset_torque()
        self.body.add_torque(angular_force)
        self.body.update(dt)
        self.body.position = vector.Vec2(self.body.position.x % 640.0,
                                         self.body.position.y % 480.0)
        self.body.angle %= 2.0 * math.pi

class Server(object):
    """Handle updating entities and socket server"""
    def __init__(self, sock_server, quitcmd, spawncmd, destroycmd, updatecmd,
                 players, idalloc):
        self.sock_server = sock_server
        self.quitcmd = quitcmd
        self.spawncmd = spawncmd
        self.destroycmd = destroycmd
        self.updatecmd = updatecmd
        self.players = players
        self.idalloc = idalloc

    def on_hello(self, address):
        if address not in self.players:
            newid = self.idalloc.fetch()
            boxman = ServerBoxman(newid)
            for sendto, player in self.players.iteritems():
                # Notify new player of existing players
                self.spawncmd.send(ENT_BOXMAN, player, address)
                # Notify existing players of new player
                self.spawncmd.send(ENT_BOXMAN, boxman, sendto)
            self.players[address] = boxman
            # Notify new player of its entity
            self.spawncmd.send(ENT_PLAYER, boxman, address)
            logger.debug("Hello:New client:%s", repr(address))
        else:
            logger.debug("Hello:Client already known")

    def on_quit(self, address):
        if address in self.players:
            oldid = self.players[address].id
            self.idalloc.free(oldid)
            del self.players[address]
            self.quitcmd.send(address)
            logger.debug("Quit:Client %s", repr(address))
            for address in self.players.iterkeys():
                self.destroycmd.send(oldid, address)
        else:
            logger.debug("Quit:Client unknown")

    def on_client(self, movement, address):
        if address not in self.players:
            logger.debug("Client:Client unknown")
            return
        self.players[address].set_movement(movement)

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
    headpack = command.HeaderPack(sock_writequeue)
    cmdpack = command.CommandPack(headpack)
    quitcmd = command.QuitCommand(cmdpack)
    spawncmd = command.SpawnCommand(cmdpack)
    destroycmd = command.DestroyCommand(cmdpack)
    updatecmd = command.UpdateCommand(cmdpack)
    hello_dispatcher = dispatch.HelloDispatch()
    quit_dispatcher = dispatch.QuitDispatch()
    client_dispatcher = dispatch.ClientDispatch(players)

    cmd_dispatcher = dispatch.CommandDispatch()
    cmd_dispatcher.push_handlers(received_hello=hello_dispatcher.dispatch,
                                 received_quit=quit_dispatcher.dispatch,
                                 received_client=client_dispatcher.dispatch)
    header_dispatcher = dispatch.HeaderDispatch()
    header_dispatcher.push_handlers(received_header=cmd_dispatcher.dispatch)

    sock_dispatcher = sockwrap.SocketReadDispatch(header_dispatcher)
    sock = sockwrap.create_server_socket(address, port)
    sock_server = sockwrap.SocketServer(sock_dispatcher, sock_writequeue, sock)
    server = Server(sock_server, quitcmd, spawncmd, destroycmd, updatecmd,
                    players, idalloc)
    hello_dispatcher.push_handlers(server)
    quit_dispatcher.push_handlers(server)
    client_dispatcher.push_handlers(server)
    return server
