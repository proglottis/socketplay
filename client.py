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

import pyglet

from protocol import command, dispatch
from protocol.local import *
import sockwrap

logger = logging.getLogger(__name__)

def image_player_color(image, mask, color):
    mask_data = mask.get_image_data().get_data('L', mask.width)
    image_data = image.get_image_data().get_data('RGBA', image.width * 4)
    new_data = ""
    for index, alpha in enumerate(mask_data):
        alpha_ord = ord(alpha)
        if alpha_ord > 0:
            new_data += chr(color[0]) + \
                        chr(color[1]) + \
                        chr(color[2]) + \
                        image_data[index*4+3]
        else:
            new_data += image_data[index*4] + \
                        image_data[index*4+1] + \
                        image_data[index*4+2] + \
                        image_data[index*4+3]
    image.get_image_data().set_data('RGBA', image.width * 4, new_data)
    return pyglet.image.ImageData(image.width, image.height, "RGBA", new_data,
                                  image.width * 4)

class ClientBoxman(pyglet.sprite.Sprite):
    """Client Boxman entity"""
    def __init__(self, color, batch=None, group=None):
        super(ClientBoxman, self).__init__(
                image_player_color(pyglet.resource.image('boxman.png'),
                                   pyglet.resource.image('boxman-color.png'),
                                   color),
                batch=batch, group=group)

class ClientBoxmanFactory(object):
    """Client Boxman entity factory"""
    def __init__(self, batch):
        self.batch = batch

    def create(self, color):
        return ClientBoxman(color, batch=self.batch)

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
        self.north = False
        self.east = False
        self.south = False
        self.west = False
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

    def on_update_entity(self, id, pos, address):
        if id not in self.players:
            return
        self.players[id].set_position(*pos)

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

    def draw(self):
        self.batch.draw()

Client.register_event_type('on_client_quit')

def create_client(address, port=11235):
    """Client creation factory method"""
    players = {}
    batch = pyglet.graphics.Batch()
    boxmanfactory = ClientBoxmanFactory(batch)

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
