"""
Game client
"""
# Copyright (C) 2008 James Fargher

# This program is free software. It comes without any warranty, to
# the extent permitted by applicable law. You can redistribute it
# and/or modify it under the terms of the Do What The Fuck You Want
# To Public License, Version 2, as published by Sam Hocevar. See
# http://sam.zoy.org/wtfpl/COPYING for more details.

import logging
import math

import pyglet

from util import ColoredSprite
from protocol import command, dispatch
from protocol.local import *
import sockwrap

logger = logging.getLogger(__name__)

class ClientBoxman(ColoredSprite):
    """Client Boxman entity"""
    def __init__(self, color, batch=None, group=None):
        super(ClientBoxman, self).__init__(
                pyglet.resource.image('boxman.png'),
                pyglet.resource.image('boxman-color.png'), color,
                batch=batch, group=group)
        self.image.anchor_x = self.width // 2
        self.image.anchor_y = self.height // 2
        self.vel_x = 0.0
        self.vel_y = 0.0

    def set_velocity(self, x, y):
        self.vel_x = x
        self.vel_y = y

    def update(self, dt):
        self.set_position(self.x + self.vel_x * dt, self.y + self.vel_y * dt)

class Client(pyglet.event.EventDispatcher):
    """Handle updating and rendering client entities and socket server"""
    def __init__(self, batch, sock_server, hellocmd, quitcmd, clientcmd,
                 sendto, players):
        self.batch = batch
        self.sock_server = sock_server
        self.hellocmd = hellocmd
        self.quitcmd = quitcmd
        self.clientcmd = clientcmd
        self.sendto = sendto
        self.players = players
        self.forward = False
        self.backward = False
        self.rot_cw = False
        self.rot_ccw = False
        self.changed = False

    def on_quit(self, address):
        self.dispatch_event('on_client_quit')

    def on_spawn_entity(self, type, id, color, address):
        logger.debug("Spawn:Entity %d" % id)
        if type == ENT_PLAYER:
            logger.debug("Spawn:ENT_PLAYER")
            self.players[id] = ClientBoxman(color, batch=self.batch)
        elif type == ENT_BOXMAN:
            logger.debug("Spawn:ENT_BOXMAN")
            self.players[id] = ClientBoxman(color, batch=self.batch)
        else:
            logger.warning("Spawn:Unknown type")

    def on_destroy_entity(self, id, address):
        if id in self.players:
            logger.debug("Destroy:Entity %d" % id)
            del self.players[id]
        else:
            logger.warning("Destroy:Unknown entity %d" % id)

    def on_update_entity(self, id, pos, direction, velocity, address):
        if id not in self.players:
            return
        self.players[id].set_position(*pos)
        self.players[id].rotation = math.degrees(direction)
        self.players[id].set_velocity(*velocity)

    def send_hello(self):
        self.hellocmd.send(self.sendto)

    def send_quit(self):
        self.quitcmd.send(self.sendto)

    def send_client(self):
        if self.changed:
            dir = (self.forward, self.backward, self.rot_cw, self.rot_ccw)
            self.clientcmd.send(dir, self.sendto)
            self.changed = False

    def start_move(self, forward=False, backward=False,
                   rot_cw=False, rot_ccw=False):
        self.forward = self.forward or forward
        self.backward = self.backward or backward
        self.rot_cw = self.rot_cw or rot_cw
        self.rot_ccw = self.rot_ccw or rot_ccw
        self.changed = forward or backward or rot_cw or rot_ccw

    def stop_move(self, forward=False, backward=False,
                   rot_cw=False, rot_ccw=False):
        self.forward = self.forward and not forward
        self.backward = self.backward and not backward
        self.rot_cw = self.rot_cw and not rot_cw
        self.rot_ccw = self.rot_ccw and not rot_ccw
        self.changed = forward or backward or rot_cw or rot_ccw

    def update(self, dt):
        self.send_client()
        self.sock_server.update()
        for player in self.players.itervalues():
            player.update(dt)

    def draw(self):
        self.batch.draw()

Client.register_event_type('on_client_quit')

def create_client(address, port=11235):
    """Client creation factory method"""
    players = {}
    batch = pyglet.graphics.Batch()
    quit_dispatcher = dispatch.QuitDispatch()
    spawn_dispatcher = dispatch.SpawnDispatch()
    destroy_dispatcher = dispatch.DestroyDispatch()
    update_dispatcher = dispatch.UpdateDispatch()
    cmd_dispatcher = dispatch.CommandDispatch()
    cmd_dispatcher.push_handlers(received_quit=quit_dispatcher.dispatch,
                                 received_spawn=spawn_dispatcher.dispatch,
                                 received_destroy=destroy_dispatcher.dispatch,
                                 received_update=update_dispatcher.dispatch)

    header_dispatcher = dispatch.HeaderDispatch()
    header_dispatcher.push_handlers(received_header=cmd_dispatcher.dispatch)

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
    quit_dispatcher.push_handlers(client)
    spawn_dispatcher.push_handlers(client)
    destroy_dispatcher.push_handlers(client)
    update_dispatcher.push_handlers(client)
    return client
